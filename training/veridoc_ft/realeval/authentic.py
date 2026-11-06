"""Authentic filing-TEXT evaluation: retrieval + extraction over REAL 10-K text.

This is the eval the project has flagged as the release blocker since Phase
4C: every number so far was measured on *templated prose* wrapping authentic
XBRL values. Here the corpus is the **verbatim text of the actual 10-K
filings** (fetched from SEC EDGAR archives by accession number — the same
accessions the benchmark's gold facts came from), so the system faces real
filing language: "Total net sales" instead of "total revenue", values in
tables whose scale lives in a column header, boilerplate, and hundreds of
pages of distractor prose.

Honesty notes, by construction:

- Evidence is NEVER paraphrased or generated: HTML is converted to plain text
  verbatim (tags stripped, table cells joined with " | ", hidden inline-XBRL
  containers dropped). Layout is lost — this is an authentic-*text* eval, not
  an authentic-*layout* eval, and results must say so.
- Gold = the benchmark's authoritative XBRL facts, restricted to targets whose
  value is a whole number of millions (filings print "391,035" under an
  "in millions" header; raw-dollar gold cannot be text-matched honestly).
  Each company's corpus document is its LATEST 10-K, and gold covers that
  filing's fiscal year and the prior year (comparatives printed in the same
  statements).
- Real tables state scale out-of-band, so two matching regimes are reported:
  scale-aware (`value_exact`, the normalizer as everywhere else) and
  scale-agnostic (`value_digits_exact`, exact digit-string match). A model
  reading "391,035" from a table cannot know the unit from the chunk alone;
  the digits metric credits the read, the scale-aware metric does not — both
  are reported, neither is hidden.
- Retrieval-hit is likewise reported in both regimes so retrieval misses are
  not charged to the extractor (same accounting as the e2e harness).
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from http import client
from pathlib import Path

from veridoc_ft.config import TrainConfig
from veridoc_ft.realeval.dataset import RealExample, _require_contact_ua, load_real
from veridoc_ft.realeval.e2e import ExtractFn, GatewayClient, _default_extract_fn, _slug, build_pdf
from veridoc_ft.realeval.evaluate import aggregate, passage_contains_gold
from veridoc_ft.realeval.normalize import periods_match, values_match

_ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
_REQUEST_DELAY_S = 0.25
# Page budget fed to the deterministic PDF builder; the ingestion pipeline
# then chunks pages further (800/150 chars). Ingestion caps documents at 300
# pages, and the renderer fits 46 lines of 14pt leading on a LETTER page — the
# line cap keeps one logical page = one physical page, or overflow pages would
# push a 290-page document past the gateway's 300-page limit.
_PAGE_CHARS = 6400
_PAGE_LINES = 46
_MAX_PAGES = 290

# Number tokens as printed in filings ("391,035", "1,234.5").
_NUM_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?")

# HTML void elements never get a matching end tag.
_VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
# Elements whose content never belongs in the text. <head> is deliberately NOT
# skipped as a container: its closing tag is legally omittable and treating it
# as a skip root can swallow the whole body; everything meaningful inside it
# (script/style/title) is skipped individually and the rest is void tags.
_SKIP_TAGS = {"script", "style", "title"}
_BLOCK_TAGS = {
    "p", "div", "tr", "table", "li", "ul", "ol", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6", "br",
}


class _FilingTextExtractor(HTMLParser):
    """Strip a filing's HTML to plain text, preserving table rows as lines.

    Table cells are joined with " | " so a statement row survives as e.g.
    "Total net sales | 391,035 | 383,285". Hidden containers (the inline-XBRL
    header and other display:none elements) are dropped entirely — their
    machine-readable facts are NOT part of the text a human reads, and leaking
    them would quietly turn this back into an oracle eval.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        # Stack of OPEN tag names inside a skipped subtree. A name stack (not a
        # bare counter) is what makes real-world HTML safe: legally-omitted end
        # tags (<p>, <td>, <tr>…) are implied-closed when an ancestor closes,
        # and STRAY end tags with no matching start are ignored. A counter gets
        # both wrong — it either swallows the rest of the document or leaks the
        # hidden inline-XBRL facts this parser exists to drop.
        self._skip_stack: list[str] = []

    @staticmethod
    def _hidden(attrs: list[tuple[str, str | None]]) -> bool:
        style = next((v for k, v in attrs if k == "style" and v), "") or ""
        style = re.sub(r"\s+", "", style).lower()
        return "display:none" in style or "visibility:hidden" in style

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._skip_stack:
            if tag not in _VOID:
                self._skip_stack.append(tag)
            return
        if (tag in _SKIP_TAGS or self._hidden(attrs)) and tag not in _VOID:
            self._skip_stack.append(tag)
            return
        if tag in ("td", "th"):
            self.parts.append(" | ")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._skip_stack:
            if tag in self._skip_stack:
                # Implied-close any unclosed children, then close `tag` itself.
                while self._skip_stack and self._skip_stack[-1] != tag:
                    self._skip_stack.pop()
                if self._skip_stack:
                    self._skip_stack.pop()
            # Stray end tags (no matching start) are ignored — they must not
            # terminate the skip early and leak hidden content.
            return
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_stack and data:
            # Source newlines are soft whitespace in HTML; only block tags
            # produce real line breaks (filings wrap rows across source lines).
            self.parts.append(data.replace("\r", " ").replace("\n", " "))


def html_to_text(html: str) -> str:
    """Verbatim text of the filing: entities decoded, tags stripped, rows kept."""
    parser = _FilingTextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    # Normalize ALL horizontal whitespace to plain spaces — filings use en/em/
    # thin/figure/narrow-no-break spaces for number padding, and anything that
    # survives as a "word character" defeats line wrapping downstream.
    text = re.sub(r"[^\S\n]+", " ", text)
    lines = []
    for raw in text.splitlines():
        # Collapse runs of empty table cells and trim dangling separators so
        # a sparse statement row reads "Total net sales | 391,035 | 383,285".
        line = re.sub(r"(?:\s*\|\s*){2,}", " | ", raw).strip().strip("|").strip()
        lines.append(line)
    return re.sub(r"\n{2,}", "\n", "\n".join(lines)).strip()


def _wrap(line: str, width: int = 160) -> list[str]:
    """Word-wrap one line, hard-slicing space-free runs longer than `width`.

    The PDF renderer draws at most 200 chars per line; any line that reaches
    it longer than that is silently truncated, so the <= width invariant must
    hold even for unbreakable tokens (URLs, dot leaders, identifiers)."""
    if len(line) <= width:
        return [line]
    out: list[str] = []
    current = ""
    for word in line.split(" "):
        while len(word) > width:
            if current:
                out.append(current)
                current = ""
            out.append(word[:width])
            word = word[width:]
        if current and len(current) + 1 + len(word) > width:
            out.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        out.append(current)
    return out


def paginate(
    text: str,
    page_chars: int = _PAGE_CHARS,
    max_pages: int = _MAX_PAGES,
    page_lines: int = _PAGE_LINES,
) -> list[str]:
    """Split filing text into wrapped pages at line boundaries (deterministic).

    Bounded by BOTH chars and line count: the line cap keeps every logical
    page on a single rendered page, so the document's physical page count
    never exceeds `max_pages` and the ingestion limit.
    """
    pages: list[str] = []
    current: list[str] = []
    size = 0
    for raw in text.splitlines():
        for line in _wrap(raw):
            full = (size + len(line) + 1 > page_chars) or (len(current) >= page_lines)
            if full and current:
                pages.append("\n".join(current))
                current, size = [], 0
                if len(pages) >= max_pages:
                    return [p for p in pages if p.strip()]
            current.append(line)
            size += len(line) + 1
    if current and len(pages) < max_pages:
        pages.append("\n".join(current))
    return [p for p in pages if p.strip()]


def _get(url: str, ua: str, retries: int = 4) -> bytes:
    """Fetch one EDGAR archive URL with fair-access pacing and backoff.

    Honors Retry-After (SEC throttle blocks are minutes, not seconds) and
    retries mid-body connection failures, which urllib raises raw rather than
    wrapped in URLError.
    """
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    for attempt in range(retries):
        time.sleep(_REQUEST_DELAY_S)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                return bytes(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429, 500, 502, 503, 504) and attempt < retries - 1:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else float(2**attempt)
                )
                time.sleep(delay)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, client.HTTPException):
            if attempt < retries - 1:
                time.sleep(2**attempt)
                continue
            raise
    raise RuntimeError(f"unreachable: {url}")


def fetch_filing_html(
    cik: str, accession: str, cache_dir: Path, ua: str | None = None
) -> tuple[str, str]:
    """Fetch the primary 10-K document for an accession (cached on disk).

    Returns ``(html, document_name)``. The primary document is selected as the
    largest .htm in the filing index — EDGAR filings carry exhibits and
    wrapper pages, and the full 10-K body is reliably the largest HTML member.
    The picked name is recorded in the report so a wrong pick is visible.
    """
    ua = ua or _require_contact_ua()
    accn = accession.replace("-", "")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{accn}.htm"
    name_file = cache_dir / f"{accn}.name"
    if cached.exists() and cached.stat().st_size > 0:
        name = name_file.read_text(encoding="utf-8") if name_file.exists() else "cached"
        return cached.read_text(encoding="utf-8", errors="replace"), name

    index = json.loads(_get(f"{_ARCHIVES}/{int(cik)}/{accn}/index.json", ua).decode("utf-8"))
    items = [
        i for i in index["directory"]["item"]
        if str(i.get("name", "")).lower().endswith((".htm", ".html"))
        and "index" not in str(i.get("name", "")).lower()
    ]
    if not items:
        raise RuntimeError(f"no HTML documents in filing {accession}")
    primary = max(items, key=lambda i: int(i.get("size") or 0))
    html = _get(f"{_ARCHIVES}/{int(cik)}/{accn}/{primary['name']}", ua).decode(
        "utf-8", errors="replace"
    )
    # Atomic cache write: a killed run must not leave a truncated file that
    # every later run silently trusts as the whole filing.
    tmp = cache_dir / f"{accn}.htm.tmp"
    tmp.write_text(html, encoding="utf-8")
    tmp.replace(cached)
    name_file.write_text(str(primary["name"]), encoding="utf-8")
    return html, str(primary["name"])


@dataclass(frozen=True)
class GoldItem:
    company: str
    metric: str
    period: str
    value: str
    unit: str

    @property
    def question(self) -> str:
        return f"What was {self.company}'s {self.metric} for {self.period}?"

    @property
    def gold(self) -> dict:
        return {
            "metric": self.metric, "value": self.value, "unit": self.unit,
            "period": self.period, "evidence": None, "supported": True,
        }


@dataclass(frozen=True)
class FilingSpec:
    company: str
    cik: str
    accession: str
    items: tuple[GoldItem, ...]


def _period_year(period: str) -> int | None:
    m = re.search(r"(\d{4})", period or "")
    return int(m.group(1)) if m else None


def select_gold(examples: list[RealExample]) -> list[FilingSpec]:
    """Latest 10-K per company + XBRL gold for its FY and FY-1 comparatives.

    Only `answerable` benchmark targets whose value is a whole number of
    millions qualify (see module docstring); one item per (metric, period).
    """
    answerable = [
        e for e in examples
        if e.category == "answerable" and e.target.get("unit") == "USD millions"
    ]
    specs: list[FilingSpec] = []
    for company in sorted({e.company for e in answerable}):
        rows = [e for e in answerable if e.company == company]
        latest = max(rows, key=lambda e: str(e.provenance.get("period_end", "")))
        fy = _period_year(str(latest.target["period"]))
        if fy is None or not latest.provenance.get("accession"):
            continue
        allowed = {f"FY{fy}", f"FY{fy - 1}"}
        seen: set[tuple[str, str]] = set()
        items: list[GoldItem] = []
        for e in sorted(rows, key=lambda e: e.id):
            period = str(e.target["period"])
            key = (str(e.target["metric"]), period)
            if period in allowed and key not in seen:
                seen.add(key)
                items.append(GoldItem(
                    company=company, metric=str(e.target["metric"]), period=period,
                    value=str(e.target["value"]), unit=str(e.target["unit"]),
                ))
        if items:
            specs.append(FilingSpec(
                company=company, cik=str(latest.provenance["cik"]),
                accession=str(latest.provenance["accession"]), items=tuple(items),
            ))
    return specs


def _canon_digits(value: object) -> str:
    """Digit-string of a printed number, exact except a trailing .0 run.

    '(391,035.0)' -> '391035' but '3,910.35' -> '391035' is NOT equal to
    '3,910' ('3910') — truncating at the decimal point would credit numbers
    the filing never printed.
    """
    s = re.sub(r"\.0+(?=\D|$)", "", str(value or ""))
    return re.sub(r"[^\d]", "", s)


def digits_scoreable(gold: dict) -> bool:
    """Whether the digits regime can score this gold value at all.

    Excluded (reported, never silently zeroed): values under 4 digits (too
    collision-prone) and values whose digit-string reads as a calendar year
    1900–2100 — a $2,023M gold would otherwise 'match' every fiscal-year date
    token in the filing.
    """
    gd = _canon_digits(gold.get("value"))
    if len(gd) < 4:
        return False
    return not (len(gd) == 4 and 1900 <= int(gd) <= 2100)


def passage_has_gold_digits(passage: str, gold: dict) -> bool:
    """Scale-agnostic support: some number token prints the gold digits.

    Tokens are matched individually (never a digits-substring of the whole
    passage, which would false-positive across adjacent table cells). Callers
    must gate on `digits_scoreable(gold)`.
    """
    gd = _canon_digits(gold.get("value"))
    if not digits_scoreable(gold):
        return False
    return any(_canon_digits(tok) == gd for tok in _NUM_TOKEN.findall(passage))


def score_authentic(item: GoldItem, retrieved_texts: list[str], pred: dict) -> dict:
    gold = item.gold
    status = pred["status"]
    result = pred["result"]
    schema_valid = status == "ok"
    markers = {f"E{i + 1}" for i in range(len(retrieved_texts))}

    s: dict[str, object] = {
        "id": f"{item.company}|{item.metric}|{item.period}",
        "company": item.company,
        "metric": item.metric,
        "period": item.period,
        "category": "authentic",
        "json_parse": status in {"ok", "schema_invalid"},
        "schema_valid": schema_valid,
        "latency_s": pred["latency_s"],
        "gold_supported": True,
        "pred_supported": bool(result["supported"]) if schema_valid else False,
        "retrieval_hit": any(passage_contains_gold(t, gold) for t in retrieved_texts),
    }
    pv = result.get("value") if schema_valid else None
    pu = result.get("unit") if schema_valid else None
    s["value_exact"] = schema_valid and values_match(pv, pu, gold["value"], gold["unit"])
    s["metric_exact"] = schema_valid and (
        (result.get("metric") or "").strip().lower() == item.metric.strip().lower()
    )
    s["period_correct"] = schema_valid and periods_match(result.get("period"), item.period)
    s["citation_valid"] = schema_valid and result.get("evidence") in markers

    # Digits-regime keys exist ONLY for digits-scoreable gold; otherwise the
    # item is excluded from every digits denominator and counted as excluded,
    # never hardwired False.
    if digits_scoreable(gold):
        s["retrieval_hit_digits"] = any(
            passage_has_gold_digits(t, gold) for t in retrieved_texts
        )
        s["value_digits_exact"] = (
            schema_valid
            and bool(s["pred_supported"])
            and _canon_digits(pv) == _canon_digits(gold["value"])
        )
        cited_idx = -1
        if s["citation_valid"]:
            cited_idx = int(str(result.get("evidence"))[1:]) - 1
        s["citation_support_digits"] = 0 <= cited_idx < len(retrieved_texts) and (
            passage_has_gold_digits(retrieved_texts[cited_idx], gold)
        )
    return s


def run_authentic(
    config: TrainConfig,
    data_path: str,
    gateway_url: str = "http://localhost:3000",
    adapter_path: str | None = None,
    top_k: int = 5,
    rerank: bool | None = True,
    limit: int | None = None,
    out_path: str | None = None,
    cache_dir: str = "data/authentic",
    client: GatewayClient | None = None,
    extract_fn: ExtractFn | None = None,
    specs: list[FilingSpec] | None = None,
    filing_text: dict[str, str] | None = None,
    retrieval_only: bool = False,
) -> dict:
    """Fetch filings, ingest verbatim text, then retrieve + extract + score.

    `specs`/`filing_text` are injectable for tests; by default gold comes from
    the benchmark file and filings are fetched from EDGAR (disk-cached).
    """
    if specs is None:
        specs = select_gold(load_real(data_path))
    client = client or GatewayClient(gateway_url, timeout_s=600.0)

    corpus_stats: list[dict] = []
    document_ids: list[str] = []
    for spec in specs:
        source_doc = "injected"
        if filing_text is not None:
            text = filing_text[spec.company]
        else:
            html, source_doc = fetch_filing_html(spec.cik, spec.accession, Path(cache_dir))
            text = html_to_text(html)
            if len(text) < 10_000:
                # A real 10-K body is hundreds of KB of text; this means the
                # parser dropped the document or the pick was a stub page.
                raise RuntimeError(
                    f"extracted only {len(text)} chars from {spec.accession} "
                    f"({source_doc}) — refusing to eval on a truncated corpus"
                )
        pages = paginate(text)
        filename = f"{_slug(spec.company)}-10k-{spec.accession.replace('-', '')}.pdf"
        document_id = client.upload_pdf(filename, build_pdf(pages))
        document_ids.append(document_id)
        corpus_stats.append({
            "company": spec.company, "accession": spec.accession,
            "source_document": source_doc, "pages": len(pages),
            "chars": len(text), "document_id": document_id,
        })

    items = [item for spec in specs for item in spec.items]
    if limit:
        items = items[:limit]

    if not retrieval_only:
        extract_fn = extract_fn or _default_extract_fn(config, adapter_path)

    retrieval_meta: dict = {}
    scores: list[dict] = []
    details: list[dict] = []
    for item in items:
        # Retrieval is scoped to THIS eval's documents: anything else sitting
        # in the store (e.g. the e2e harness's templated digests) would hand
        # the model oracle-phrased evidence and quietly fake the results.
        retrieved = client.retrieve(
            item.question, top_k=top_k, rerank=rerank, document_ids=document_ids
        )
        texts = [str(p.get("text", "")) for p in retrieved]
        if not retrieval_meta and retrieved:
            retrieval_meta = dict(getattr(client, "last_response_meta", {}))
            if rerank is True and not retrieval_meta.get("reranked"):
                raise RuntimeError(
                    "rerank=on was requested but the stack performed no "
                    "reranking (no reranker configured?) — refusing to "
                    "publish a report whose header misstates the config"
                )
        if retrieval_only:
            # Measure the retrieval leg alone (no model, no GPU): used to
            # quantify retrieval changes like query expansion in isolation.
            gold = item.gold
            s = {
                "id": f"{item.company}|{item.metric}|{item.period}",
                "company": item.company, "metric": item.metric,
                "period": item.period, "category": "authentic",
                "latency_s": 0.0,
                "retrieval_hit": any(passage_contains_gold(t, gold) for t in texts),
            }
            if digits_scoreable(gold):
                s["retrieval_hit_digits"] = any(
                    passage_has_gold_digits(t, gold) for t in texts
                )
            raw = ""
        else:
            assert extract_fn is not None
            pred = extract_fn(item.question, texts)
            s = score_authentic(item, texts, pred)
            raw = str(pred.get("raw", ""))[:400]
        scores.append(s)
        details.append({
            **s,
            "question": item.question,
            "gold_value": item.value,
            "retrieved": [str(p.get("citation", "")) for p in retrieved],
            "raw": raw,
        })

    metrics = aggregate(scores)
    extra_keys = (
        "retrieval_hit", "retrieval_hit_digits",
        "value_digits_exact", "citation_support_digits",
    )
    for key in extra_keys:
        vals = [bool(x[key]) for x in scores if key in x]
        metrics[f"{key}_rate"] = round(sum(vals) / len(vals), 4) if vals else None
    hit = [s for s in scores if s.get("retrieval_hit_digits")]
    if retrieval_only:
        metrics["n_digits_excluded"] = sum(
            1 for s in scores if "retrieval_hit_digits" not in s
        )
        metrics["value_digits_given_hit"] = None
        metrics["false_abstention_rate"] = None
        metrics["parse_failure_rate"] = None
    else:
        metrics["n_digits_excluded"] = sum(1 for s in scores if "value_digits_exact" not in s)
        metrics["value_digits_given_hit"] = (
            round(sum(bool(s.get("value_digits_exact")) for s in hit) / len(hit), 4)
            if hit
            else None
        )
        # Abstention on an answerable item is a coverage failure ONLY when the
        # model actually produced a schema-valid abstention; unparseable output
        # is a parse failure and must not masquerade as deliberate abstention.
        metrics["false_abstention_rate"] = (
            round(
                sum(bool(s["schema_valid"]) and not s["pred_supported"] for s in scores)
                / len(scores),
                4,
            )
            if scores
            else None
        )
        metrics["parse_failure_rate"] = (
            round(sum(not s["schema_valid"] for s in scores) / len(scores), 4)
            if scores
            else None
        )

    per_company = {
        spec.company: aggregate([s for s in scores if s["company"] == spec.company])
        for spec in specs
    }

    report = {
        "mode": "authentic-retrieval-only" if retrieval_only else "authentic-filing-text",
        "model_id": None if retrieval_only else config.model_id,
        "model_revision": None if retrieval_only else config.model_revision,
        "adapter": adapter_path,
        "gateway": gateway_url,
        "top_k": top_k,
        "rerank": rerank,
        "retrieval_meta": retrieval_meta,
        "corpus": corpus_stats,
        "n_items": len(items),
        "metrics": metrics,
        "per_company": per_company,
        "details": details,
    }
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Authentic filing-text evaluation (real 10-K text, XBRL gold)"
    )
    ap.add_argument("--data", default="data/realeval/real_test.jsonl")
    ap.add_argument("--gateway-url", default="http://localhost:3000")
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--model-id", default=None, help="override the pinned base model")
    ap.add_argument("--model-revision", default=None)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--rerank", choices=["auto", "on", "off"], default="on")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cache-dir", default="data/authentic")
    ap.add_argument(
        "--retrieval-only",
        action="store_true",
        help="measure retrieval hits only (no model, no GPU)",
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.model_revision and not args.model_id:
        ap.error("--model-revision requires --model-id")
    if args.model_id and not args.model_revision:
        # A moving ref would make the headline eval unreproducible from its
        # own report; demand an explicit commit (ADR-0021 pinning discipline).
        ap.error("--model-id requires an explicit --model-revision (commit sha)")
    cfg = TrainConfig()
    if args.model_id:
        cfg = replace(cfg, model_id=args.model_id, model_revision=args.model_revision)
    rep = run_authentic(
        cfg,
        args.data,
        gateway_url=args.gateway_url,
        adapter_path=args.adapter,
        top_k=args.top_k,
        rerank={"auto": None, "on": True, "off": False}[args.rerank],
        limit=args.limit,
        out_path=args.out,
        cache_dir=args.cache_dir,
        retrieval_only=args.retrieval_only,
    )
    print(json.dumps(rep["metrics"], indent=2))
