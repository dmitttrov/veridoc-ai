"""Audit the real SEC benchmark BEFORE any model sees it (Phase 4C.1 Step 3).

Checks, per example:
  * answerable/multi_page/conflicting gold value is cross-checked against the
    cached authoritative XBRL fact (by cik + accession + period end);
  * the gold value actually appears in the cited evidence passage (support);
  * period label is consistent with the evidence;
  * conflicting examples carry two different values with the restatement cited;
  * unanswerable examples do NOT contain the asked metric in their evidence.

Also classifies every example's evidence as either templated prose built from
authoritative XBRL values (what the builder actually emits) or non-templated
("would-be authentic") prose, and reports the counts honestly.

Read-only: never rewrites questions/labels.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from veridoc_ft.realeval.dataset import METRICS, load_real
from veridoc_ft.realeval.normalize import canonical_period, values_match

# The builder emits only these templated prose shapes (real XBRL values inside).
_TEMPLATE_PREFIXES = ("For FY", "As originally reported,", "Restated:")


def _xbrl_value_for(
    raw_dir: Path, cik: str, metric: str, accession: str, period_end: str
) -> int | None:
    # Restrict to THIS metric's concept file(s); a single filing reports many
    # metrics under the same accession+end, so searching across files is wrong.
    for tag in METRICS.get(metric, []):
        fp = raw_dir / f"{cik}_{tag}.json"
        if not fp.exists():
            continue
        data = json.loads(fp.read_text())
        for x in data.get("units", {}).get("USD", []):
            if (
                x.get("accn") == accession
                and x.get("end") == period_end
                and x.get("fp") == "FY"
                and x.get("form") == "10-K"
            ):
                return int(x["val"])
    return None


def classify_evidence(passage: str) -> int:
    # 3 = synthetic/templated prose; 1 = non-templated (would-be authentic).
    return 3 if passage.strip().startswith(_TEMPLATE_PREFIXES) else 1


def audit(data_path: str, raw_dir: str) -> dict:
    if not Path(data_path).exists():
        sys.exit(
            f"{data_path} not found — build it first with "
            "`python -m veridoc_ft.realeval.dataset --out data/realeval`."
        )
    examples = load_real(data_path)
    raw = Path(raw_dir)

    ev_cat = {1: 0, 3: 0}
    cat_counts: dict[str, int] = {}
    failures: list[str] = []
    xbrl_checked = xbrl_ok = 0
    support_ok = period_ok = 0
    n_supported = 0

    for ex in examples:
        cat_counts[ex.category] = cat_counts.get(ex.category, 0) + 1
        # evidence classification (templated prose built from XBRL facts)
        templated = all(classify_evidence(p) == 3 for p in ex.evidence)
        ev_cat[3 if templated else 1] += 1

        gold = ex.target
        if gold["supported"]:
            n_supported += 1
            marker = gold["evidence"]
            idx = int(marker[1:]) - 1
            passage = ex.evidence[idx]
            # (a) gold value appears in cited passage
            nums = re.findall(r"\$?\(?-?[\d,]+(?:\.\d+)?\)?", passage)
            if any(values_match(n, gold["unit"], gold["value"], gold["unit"]) for n in nums):
                support_ok += 1
            else:
                failures.append(f"{ex.id}: gold value not found in cited passage")
            # (b) period consistency
            if canonical_period(gold["period"]) == canonical_period(passage):
                period_ok += 1
            else:
                failures.append(f"{ex.id}: period mismatch passage vs gold")
            # (c) cross-check against authoritative XBRL
            prov = ex.provenance
            if prov.get("accession") and prov.get("period_end") and prov.get("cik"):
                xbrl_checked += 1
                xv = _xbrl_value_for(
                    raw, prov["cik"], gold["metric"], prov["accession"], prov["period_end"]
                )
                if xv is not None and values_match(
                    str(xv), None, gold["value"], gold["unit"]
                ):
                    xbrl_ok += 1
                else:
                    failures.append(f"{ex.id}: gold != XBRL fact (accn {prov.get('accession')})")
        else:
            # unanswerable: the asked metric must NOT appear in the evidence
            asked = gold["metric"].lower()
            if any(asked in p.lower() for p in ex.evidence):
                failures.append(f"{ex.id}: unanswerable but asked metric present in evidence")

    # conflicting examples must show two distinct values + cite the restatement
    conflicting_ok = 0
    for ex in examples:
        if ex.category == "conflicting":
            nums = set()
            for p in ex.evidence:
                nums |= set(re.findall(r"\$([\d,]+)", p))
            if len(nums) >= 2 and ex.target["evidence"] == "E2":
                conflicting_ok += 1
            else:
                failures.append(f"{ex.id}: conflicting not well-formed")

    return {
        "n": len(examples),
        "category_counts": cat_counts,
        "evidence_classification": {
            "synthetic_templated_prose": ev_cat[3],
            "non_templated_prose": ev_cat[1],
        },
        "n_supported": n_supported,
        "value_in_cited_passage": f"{support_ok}/{n_supported}",
        "period_consistent": f"{period_ok}/{n_supported}",
        "xbrl_crosscheck": f"{xbrl_ok}/{xbrl_checked}",
        "conflicting_well_formed": conflicting_ok,
        "failures": failures,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/realeval/real_test.jsonl")
    ap.add_argument("--raw", default="data/realeval/raw")
    args = ap.parse_args()
    report = audit(args.data, args.raw)
    print(json.dumps(report, indent=2))
