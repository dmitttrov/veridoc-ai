"""End-to-end RAG real evaluation: retrieval + extraction over INGESTED real docs.

This is the Step 3B harness that `realeval.evaluate` deliberately left out: the
SEC benchmark's evidence passages are rendered into deterministic per-company
PDF "filing digests", ingested through the production edge (the NestJS gateway's
upload endpoint → services/ai hybrid retrieval over Postgres+pgvector), and each
benchmark question is answered from the passages hybrid retrieval ACTUALLY
returns — not the oracle evidence. Extraction output is scored with the same
oracle gold + financial normalizer as the oracle eval, so oracle-vs-e2e deltas
isolate what retrieval costs.

Two honesty-critical differences from oracle mode:

- **Gold rewriting.** An oracle "unanswerable" example withholds the asked
  metric from its evidence — but the ingested corpus usually CONTAINS that
  metric (it is some other example's answer). Scoring abstention as correct
  there would reward failure, so gold is re-derived against the corpus: if the
  asked (company, metric, period) fact exists in the corpus, the example
  becomes answerable with that authoritative value (flagged `rewritten`).
- **Retrieval-hit accounting.** For every supported example we record whether
  ANY retrieved passage contains the gold value (`retrieval_hit`), and report
  extraction accuracy both overall and conditioned on a hit, so retrieval
  misses are never silently charged to the extractor (or hidden by it).

The harness talks only to the gateway over HTTP (ADR-0023: training and
services/ai stay separate packages), so it needs the compose stack up:
db + ai + api. Ingestion is idempotent (deterministic PDFs → stable content
hashes), so re-runs do not duplicate documents.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from typing import Any

from veridoc_ft.config import TrainConfig
from veridoc_ft.realeval.dataset import RealExample, load_real
from veridoc_ft.realeval.evaluate import aggregate, passage_contains_gold, score_real

# Matches the exact template `dataset._passage` writes, so the complete facts
# index (including distractor-only facts) can be recovered from passage text.
_FACT_RE = re.compile(
    r"^For (?P<period>FY\d{4}), (?P<company>.+?) reported (?P<metric>.+?) of "
    r"\$(?P<value>\(?[\d,]+\)?)(?P<millions> million)?\.$"
)
_QUESTION_PERIOD_RE = re.compile(r"\bfor (FY\d{4})\?$")

# A prediction-shaped dict as returned by `infer.extract`.
ExtractFn = Callable[[str, list[str]], dict]


def _slug(name: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


FactsIndex = dict[tuple[str, str, str], dict]


def harvest_corpus(
    examples: list[RealExample],
) -> tuple[dict[str, list[str]], FactsIndex]:
    """Build the corpus pages and the facts index from the benchmark itself.

    Returns ``(pages_by_company, facts_index)`` where pages are deduplicated,
    sorted passage strings (one passage per PDF page → clean provenance) and
    the index maps ``(company_lower, metric_lower, period)`` to a gold-style
    fact dict. Only supported categories contribute pages: an oracle
    "unanswerable" example's evidence duplicates some answerable passage, and
    conflicting examples contribute their original+restated pair verbatim.
    """
    pages: dict[str, set[str]] = {}
    facts: FactsIndex = {}
    for ex in examples:
        if not ex.target.get("supported"):
            continue
        for passage in ex.evidence:
            pages.setdefault(ex.company, set()).add(passage.strip())
            m = _FACT_RE.match(passage.strip())
            if m:
                unit = "USD millions" if m.group("millions") else "USD"
                key = (ex.company.lower(), m.group("metric").lower(), m.group("period"))
                facts.setdefault(key, {
                    "metric": m.group("metric"),
                    "value": m.group("value"),
                    "unit": unit,
                    "period": m.group("period"),
                    "evidence": None,  # marker depends on what retrieval returns
                    "supported": True,
                })
        # Restatements: the gold (latest) figure is authoritative for lookups too.
        if ex.category == "conflicting":
            key = (ex.company.lower(), ex.target["metric"].lower(), ex.target["period"])
            facts[key] = {**ex.target, "evidence": None}
    return {c: sorted(ps) for c, ps in sorted(pages.items())}, facts


def resolve_e2e_target(ex: RealExample, facts: FactsIndex) -> tuple[dict, bool]:
    """Re-derive the gold target against the INGESTED corpus.

    Returns ``(target, rewritten)``. Only oracle-unanswerable examples can be
    rewritten (to answerable, when the asked fact exists in the corpus);
    supported examples keep their oracle gold unchanged.
    """
    if ex.target.get("supported"):
        return ex.target, False
    qm = _QUESTION_PERIOD_RE.search(ex.question.strip())
    period = qm.group(1) if qm else f"FY{str(ex.provenance.get('period_end', ''))[:4]}"
    fact = facts.get((ex.company.lower(), str(ex.target.get("metric", "")).lower(), period))
    if fact is None:
        return ex.target, False
    return dict(fact), True


def build_pdf(pages: list[str]) -> bytes:
    """Render each passage as its own PDF page (deterministic bytes).

    Mirrors services/ai's eval PDF builder: reportlab ``invariant=1`` fixes
    timestamps and the document id, so identical input produces identical
    bytes — and therefore a stable content hash, which is what makes gateway
    ingestion idempotent across re-runs. reportlab is imported lazily so the
    module stays importable without the [dev] extra.
    """
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER, invariant=1)
    _, height = LETTER
    for text in pages:
        y = height - 72
        for line in text.split("\n"):
            if y < 72:
                # Overflow onto a fresh physical page rather than drawing at
                # negative y — off-page text survives only by a pypdf quirk
                # and is invisible to humans or geometry-aware extractors.
                c.showPage()
                y = height - 72
            c.drawString(72, y, line[:200])
            y -= 14
        c.showPage()
    c.save()
    return buf.getvalue()


class GatewayClient:
    """Minimal stdlib HTTP client for the public gateway (no new dependencies).

    Talks to the production edge — POST /api/documents/upload (multipart) and
    POST /api/retrieve — never to the internal AI service directly.
    """

    _BOUNDARY = "veridoc-e2e-multipart-boundary"

    def __init__(self, base_url: str, timeout_s: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        # Identity of the retrieval configuration actually used, captured from
        # the last /api/retrieve response so reports are self-documenting.
        self.last_response_meta: dict = {}

    def _request(self, req: urllib.request.Request) -> dict:
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
                data: dict = json.loads(resp.read().decode("utf-8"))
                return data
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"gateway {exc.code} for {req.full_url}: {body}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(
                f"gateway unreachable/timed out for {req.full_url} "
                f"(client timeout {self.timeout_s}s; for large ingests also raise "
                f"the gateway's AI_INGEST_TIMEOUT_MS): {exc}"
            ) from exc

    def upload_pdf(self, filename: str, data: bytes) -> str:
        """Upload one PDF; returns the stored documentId (idempotent re-upload ok)."""
        b = self._BOUNDARY
        head = (
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"{filename}\"\r\nContent-Type: application/pdf\r\n\r\n"
        ).encode()
        body = head + data + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/documents/upload",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={b}"},
            method="POST",
        )
        result = self._request(req)
        if result.get("state") != "succeeded":
            raise RuntimeError(f"ingestion failed for {filename}: {result}")
        return str(result["documentId"])

    def retrieve(
        self,
        query: str,
        top_k: int,
        rerank: bool | None,
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        """Hybrid retrieval; scope with `document_ids` so an eval can never be
        contaminated by other corpora sitting in the same (add-only) store."""
        payload: dict[str, Any] = {"query": query, "topK": top_k}
        if rerank is not None:
            payload["rerank"] = rerank
        if document_ids:
            payload["documentIds"] = document_ids
        req = urllib.request.Request(
            f"{self.base_url}/api/retrieve",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        result = self._request(req)
        self.last_response_meta = {
            "embedding_model": result.get("embeddingModel"),
            "embedding_dim": result.get("embeddingDim"),
            "reranked": result.get("reranked"),
            "reranker_model": result.get("rerankerModel"),
        }
        passages = result.get("passages", [])
        return list(passages)


def _ingest_corpus(
    client: GatewayClient, pages_by_company: dict[str, list[str]]
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for company, pages in pages_by_company.items():
        filename = f"{_slug(company)}-sec-digest.pdf"
        mapping[filename] = client.upload_pdf(filename, build_pdf(pages))
    return mapping


def _default_extract_fn(config: TrainConfig, adapter_path: str | None) -> ExtractFn:
    from veridoc_ft.infer import extract, load_model  # lazy: needs torch + weights

    model, tokenizer = load_model(config, adapter_path)

    def fn(question: str, evidence: list[str]) -> dict:
        return extract(model, tokenizer, question, evidence, config)

    return fn


def run_e2e(
    config: TrainConfig,
    data_path: str,
    gateway_url: str = "http://localhost:3000",
    adapter_path: str | None = None,
    top_k: int = 5,
    rerank: bool | None = None,
    limit: int | None = None,
    out_path: str | None = None,
    client: GatewayClient | None = None,
    extract_fn: ExtractFn | None = None,
) -> dict:
    """Ingest the benchmark corpus, then retrieve + extract + score per question."""
    examples = load_real(data_path)
    pages_by_company, facts = harvest_corpus(examples)
    if limit:
        examples = examples[:limit]

    client = client or GatewayClient(gateway_url)
    started = time.perf_counter()
    document_ids = _ingest_corpus(client, pages_by_company)
    ingest_s = round(time.perf_counter() - started, 2)

    extract_fn = extract_fn or _default_extract_fn(config, adapter_path)

    scores: list[dict] = []
    details: list[dict] = []
    rewritten_count = 0
    corpus_doc_ids = list(document_ids.values())
    for ex in examples:
        target, rewritten = resolve_e2e_target(ex, facts)
        rewritten_count += int(rewritten)
        # Scoped to this eval's own documents — the store is add-only, so an
        # unscoped query could pull passages from unrelated corpora (e.g. the
        # authentic 10-K texts) ingested on the same stack.
        retrieved = client.retrieve(
            ex.question, top_k=top_k, rerank=rerank, document_ids=corpus_doc_ids
        )
        texts = [str(p.get("text", "")) for p in retrieved]

        pred = extract_fn(ex.question, texts)
        # Score against the retrieved evidence (markers, citation support) and
        # the corpus-resolved gold — the same scorer as oracle mode otherwise.
        e2e_ex = replace(ex, evidence=texts, target=target)
        s = score_real(e2e_ex, pred)
        s["rewritten"] = rewritten
        if target.get("supported"):
            s["retrieval_hit"] = any(passage_contains_gold(t, target) for t in texts)
        scores.append(s)
        details.append({
            **s,
            "question": ex.question,
            "retrieved": [
                {"text": t, "citation": str(p.get("citation", ""))}
                for t, p in zip(texts, retrieved, strict=True)
            ],
            "raw": str(pred.get("raw", ""))[:400],
        })

    metrics = aggregate(scores)
    hits = [s for s in scores if "retrieval_hit" in s]
    hit_subset = [s for s in hits if s["retrieval_hit"]]
    metrics["retrieval_hit_rate"] = (
        round(sum(s["retrieval_hit"] for s in hits) / len(hits), 4) if hits else None
    )
    metrics["value_exact_given_hit"] = (
        round(sum(bool(s.get("value_exact")) for s in hit_subset) / len(hit_subset), 4)
        if hit_subset
        else None
    )
    metrics["n_rewritten_unanswerable"] = rewritten_count

    per_category: dict[str, dict] = {}
    for cat in sorted({s["category"] for s in scores}):
        per_category[cat] = aggregate([s for s in scores if s["category"] == cat])

    report = {
        "mode": "e2e",
        "model_id": config.model_id,
        "model_revision": config.model_revision,
        "adapter": adapter_path,
        "gateway": gateway_url,
        "top_k": top_k,
        "rerank": rerank,
        "corpus": {
            "documents": len(pages_by_company),
            "pages": sum(len(p) for p in pages_by_company.values()),
            "document_ids": document_ids,
            "ingest_s": ingest_s,
        },
        "metrics": metrics,
        "per_category": per_category,
        "details": details,
    }
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="End-to-end RAG real evaluation (retrieval + extraction)"
    )
    ap.add_argument("--data", default="data/realeval/real_test.jsonl")
    ap.add_argument("--gateway-url", default="http://localhost:3000")
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument(
        "--rerank",
        choices=["auto", "on", "off"],
        default="auto",
        help="auto = server default (reranker applied iff configured)",
    )
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rerank_flag = {"auto": None, "on": True, "off": False}[args.rerank]
    rep = run_e2e(
        TrainConfig(),
        args.data,
        gateway_url=args.gateway_url,
        adapter_path=args.adapter,
        top_k=args.top_k,
        rerank=rerank_flag,
        limit=args.limit,
        out_path=args.out,
    )
    print(json.dumps(rep["metrics"], indent=2))
