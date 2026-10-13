"""Build a REAL financial-extraction test set from SEC EDGAR XBRL.

Ground truth = authoritative `companyconcept` facts (exact value, unit, period,
filing accession). Network fetching is isolated in `fetch_concept` / `fetch_all`
so the pure builder (`build_examples`) is unit-testable with a saved fixture.

Categories produced: answerable, multi_page, conflicting (real restatements:
same fiscal period reported with different values across filings), and
unanswerable (ask a metric absent from the provided evidence). Evidence is
phrased in real-filing style around the REAL figure.

SEC data is public-domain US government work; the derived fixtures are kept out
of Git by default (data/ is .gitignored) but are redistributable.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from veridoc_ft.prompt import marker_for

# SEC's fair-access policy requires a descriptive User-Agent with a contact.
# Configure it via the SEC_USER_AGENT env var (do NOT hardcode a personal
# email in a public repo). The default is a non-identifying placeholder.
SEC_UA = os.environ.get(
    "SEC_USER_AGENT", "veridoc-ai-eval (set SEC_USER_AGENT to your contact)"
)

COMPANIES = [
    ("Apple Inc.", "0000320193"),
    ("Microsoft Corporation", "0000789019"),
    ("JPMorgan Chase & Co.", "0000019617"),
    ("Johnson & Johnson", "0000200406"),
    ("Walmart Inc.", "0000104169"),
    ("Exxon Mobil Corporation", "0000034088"),
]

# metric name -> candidate us-gaap concept tags (first that returns data wins).
METRICS: dict[str, list[str]] = {
    "total revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "operating income": ["OperatingIncomeLoss"],
    "net income": ["NetIncomeLoss"],
    "total assets": ["Assets"],
    "total liabilities": ["Liabilities"],
    "cash and cash equivalents": ["CashAndCashEquivalentsAtCarryingValue"],
    "net cash from operating activities": ["NetCashProvidedByUsedInOperatingActivities"],
    "stockholders equity": ["StockholdersEquity"],
}


@dataclass
class RealExample:
    id: str
    company: str
    category: str
    question: str
    evidence: list[str]
    target: dict
    provenance: dict


def fetch_concept(cik: str, tag: str) -> dict | None:
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"
    req = urllib.request.Request(url, headers={"User-Agent": SEC_UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def fetch_all(out_raw: Path) -> dict:
    """Fetch every (company, metric) concept once, cache raw JSON to disk."""
    out_raw.mkdir(parents=True, exist_ok=True)
    facts: dict = {}
    for name, cik in COMPANIES:
        facts[cik] = {"name": name, "metrics": {}}
        for metric, tags in METRICS.items():
            for tag in tags:
                data = fetch_concept(cik, tag)
                if data and data.get("units", {}).get("USD"):
                    (out_raw / f"{cik}_{tag}.json").write_text(json.dumps(data))
                    facts[cik]["metrics"][metric] = {"tag": tag, "data": data}
                    break
    return facts


_ANNUAL_FRAME = re.compile(r"^CY\d{4}(Q4I)?$")


def _is_annual(x: dict) -> bool:
    """True only for FULL-YEAR duration facts or FISCAL-YEAR-END instant facts
    in a 10-K. Critically excludes quarterly facts (e.g. frame CY2008Q2) that a
    10-K also reports for the same period end — mislabeling those as annual, or
    as 'restatements', was a real benchmark bug caught in the Phase 4C.1 audit."""
    if x.get("form") != "10-K" or not x.get("end"):
        return False
    frame = x.get("frame")
    if frame is not None:
        return bool(_ANNUAL_FRAME.match(frame))
    # Frameless: keep instants (no start) and ~full-year durations only.
    start = x.get("start")
    if not start:
        return True
    try:
        d0 = date.fromisoformat(start)
        d1 = date.fromisoformat(x["end"])
    except ValueError:
        return False
    return (d1 - d0).days >= 300


def _annual_facts(data: dict) -> list[dict]:
    """Annual (10-K) USD facts, one per fiscal-year end, latest filing wins."""
    by_period: dict[str, dict] = {}
    for x in data.get("units", {}).get("USD", []):
        if not _is_annual(x):
            continue
        key = x["end"]
        prev = by_period.get(key)
        if prev is None or x.get("filed", "") > prev.get("filed", ""):
            by_period[key] = x
    return sorted(by_period.values(), key=lambda x: x["end"])


def _period_label(end: str) -> str:
    y = re.match(r"(\d{4})", end)
    return f"FY{y.group(1)}" if y else end


def _as_millions(val: int) -> tuple[str, str]:
    """(value_string, unit_string) in filing style. Negatives use accounting
    parentheses, e.g. (42,012)."""
    if val % 1_000_000 == 0:
        mag = abs(val) // 1_000_000
        s = f"({mag:,})" if val < 0 else f"{mag:,}"
        return s, "USD millions"
    mag = abs(val)
    s = f"({mag:,})" if val < 0 else f"{mag:,}"
    return s, "USD"


def _money(vstr: str, unit: str) -> str:
    return f"${vstr} million" if unit == "USD millions" else f"${vstr}"


def _passage(company: str, metric: str, period: str, val: int) -> str:
    vstr, unit = _as_millions(val)
    return f"For {period}, {company} reported {metric} of {_money(vstr, unit)}."


def _prov(company: str, cik: str, metric: str, fact: dict) -> dict:
    return {
        "company": company, "cik": cik, "metric": metric,
        "accession": fact.get("accn"), "form": fact.get("form"),
        "fy": fact.get("fy"), "fp": fact.get("fp"), "period_end": fact.get("end"),
        "filed": fact.get("filed"), "source": "SEC EDGAR XBRL companyconcept",
    }


def build_examples(facts: dict) -> list[RealExample]:
    """Pure builder over fetched facts (no network). Deterministic."""
    out: list[RealExample] = []
    for cik, cdata in sorted(facts.items()):
        company = cdata["name"]
        metrics = cdata["metrics"]
        annual: dict[str, list[dict]] = {
            m: _annual_facts(d["data"]) for m, d in metrics.items()
        }
        metric_list = [m for m in METRICS if annual.get(m)]

        for mi, metric in enumerate(metric_list):
            rows = annual[metric][-2:]  # two most recent fiscal years
            for fact in rows:
                period = _period_label(fact["end"])
                val = int(fact["val"])
                vstr, unit = _as_millions(val)
                ans = _passage(company, metric, period, val)
                # distractor: a different metric, same company, same period if available
                other = metric_list[(mi + 1) % len(metric_list)]
                distractor = None
                for f2 in annual.get(other, []):
                    if f2["end"] == fact["end"]:
                        distractor = _passage(company, other, period, int(f2["val"]))
                        break

                # --- answerable (+ optional distractor) ---
                evid = [distractor, ans] if distractor else [ans]
                ans_idx = len(evid) - 1
                out.append(RealExample(
                    id=f"{cik}|{metric}|{period}|answerable",
                    company=company, category="answerable",
                    question=f"What was {company}'s {metric} for {period}?",
                    evidence=evid,
                    target={"metric": metric, "value": vstr, "unit": unit,
                            "period": period, "evidence": marker_for(ans_idx),
                            "supported": True},
                    provenance=_prov(company, cik, metric, fact),
                ))

                # --- unanswerable: ask a different metric not in this evidence ---
                out.append(RealExample(
                    id=f"{cik}|{metric}|{period}|unanswerable",
                    company=company, category="unanswerable",
                    question=f"What was {company}'s {other} for {period}?",
                    evidence=[ans],  # only `metric`, not `other`
                    target={"metric": other, "value": None, "unit": None,
                            "period": None, "evidence": None, "supported": False},
                    provenance=_prov(company, cik, metric, fact),
                ))

            # --- multi_page: two metrics for the latest period, ask the first ---
            if len(metric_list) >= 2 and annual[metric]:
                fact = annual[metric][-1]
                period = _period_label(fact["end"])
                val = int(fact["val"])
                vstr, unit = _as_millions(val)
                other = metric_list[(mi + 1) % len(metric_list)]
                other_fact = next(
                    (f for f in annual.get(other, []) if f["end"] == fact["end"]), None
                )
                if other_fact:
                    evid = [
                        _passage(company, other, period, int(other_fact["val"])),
                        _passage(company, metric, period, val),
                    ]
                    out.append(RealExample(
                        id=f"{cik}|{metric}|{period}|multi_page",
                        company=company, category="multi_page",
                        question=f"What was {company}'s {metric} for {period}?",
                        evidence=evid,
                        target={"metric": metric, "value": vstr, "unit": unit,
                                "period": period, "evidence": marker_for(1),
                                "supported": True},
                        provenance=_prov(company, cik, metric, fact),
                    ))

            # --- conflicting: a GENUINE restatement — the SAME full-year fact
            # reported with different values in DIFFERENT filings (accessions).
            # Only annual facts are considered, so annual-vs-quarterly pairs from
            # a single filing are never mistaken for a restatement.
            annual_usd = [x for x in metrics[metric]["data"].get("units", {}).get("USD", [])
                          if _is_annual(x)]
            by_end: dict[str, list[dict]] = {}
            for x in annual_usd:
                by_end.setdefault(x["end"], []).append(x)
            for end, group in sorted(by_end.items()):
                accns = {g.get("accn") for g in group}
                vals = {int(g["val"]) for g in group}
                # require >=2 distinct filings AND >=2 distinct values
                if len(accns) >= 2 and len(vals) >= 2:
                    g = sorted(group, key=lambda z: z.get("filed", ""))
                    original, latest = g[0], g[-1]
                    if int(original["val"]) == int(latest["val"]) or \
                            original.get("accn") == latest.get("accn"):
                        continue
                    period = _period_label(end)
                    ov, ou = _as_millions(int(original["val"]))
                    lv, lu = _as_millions(int(latest["val"]))
                    evid = [
                        f"As originally reported, {company} {metric} for {period} "
                        f"was {_money(ov, ou)}.",
                        f"Restated: {company} {metric} for {period} was revised to "
                        f"{_money(lv, lu)}, superseding the prior figure.",
                    ]
                    out.append(RealExample(
                        id=f"{cik}|{metric}|{period}|conflicting",
                        company=company, category="conflicting",
                        question=f"What was {company}'s restated {metric} for {period}?",
                        evidence=evid,
                        target={"metric": metric, "value": lv, "unit": lu,
                                "period": period, "evidence": marker_for(1),
                                "supported": True},
                        provenance=_prov(company, cik, metric, latest),
                    ))
                    break  # at most one conflicting example per (company, metric)
    return out


def build(out_dir: str = "data/realeval", built_at: str = "unknown") -> dict:
    out = Path(out_dir)
    facts = fetch_all(out / "raw")
    examples = build_examples(facts)

    path = out / "real_test.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for ex in sorted(examples, key=lambda e: e.id):
            fh.write(json.dumps(asdict(ex), sort_keys=True) + "\n")

    cats: dict[str, int] = {}
    comps: dict[str, int] = {}
    for ex in examples:
        cats[ex.category] = cats.get(ex.category, 0) + 1
        comps[ex.company] = comps.get(ex.company, 0) + 1
    card = {
        "name": "veridoc-real-eval",
        "built_at": built_at,
        "source": "SEC EDGAR XBRL companyconcept API (public domain)",
        "license": "US government work (public domain); redistributable",
        "ground_truth": "authoritative XBRL facts; no model-generated answers",
        "count": len(examples),
        "category_counts": cats,
        "company_counts": comps,
        "companies": [c[0] for c in COMPANIES],
        "metrics": list(METRICS),
    }
    (out / "real_card.json").write_text(json.dumps(card, indent=2, sort_keys=True))
    return card


def load_real(path: str) -> list[RealExample]:
    out: list[RealExample] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(RealExample(**json.loads(line)))
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Build the SEC real-eval test set")
    ap.add_argument("--out", default="data/realeval")
    ap.add_argument("--built-at", default="unknown")
    args = ap.parse_args()
    card = build(args.out, args.built_at)
    print(json.dumps(card, indent=2))
