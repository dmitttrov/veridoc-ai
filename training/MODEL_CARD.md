<!-- DRAFT model card — NOT published. Fill the metric tables from a real GPU run
     before any release. Do not invent numbers. -->
---
license: apache-2.0
base_model: Qwen/Qwen3-0.6B
tags:
  - lora
  - peft
  - financial-extraction
  - rag
library_name: peft
pipeline_tag: text-generation
---

# Veridoc Extract — LoRA adapter for structured financial-fact extraction (DRAFT)

> **Status: draft, not published.** This is a **LoRA adapter** over
> `Qwen/Qwen3-0.6B`. It is **not** a model trained from scratch and **not** a
> general financial expert. It targets one narrow task: extracting a single
> requested financial metric from provided evidence passages, as strict JSON.

## Model details

- **Developed by:** Veridoc AI (portfolio project).
- **Type:** PEFT/LoRA adapter (rank 16) for causal LM.
- **Base model:** [`Qwen/Qwen3-0.6B`](https://huggingface.co/Qwen/Qwen3-0.6B)
  @ `c1899de289a04d12100db370d81485cdf75e47ca`.
- **Language:** English (synthetic financial text).
- **License:** Apache-2.0 (adapter). Base model Apache-2.0 — attribution to
  Qwen; the base is not redistributed, only the adapter.

## Intended use

- **In scope:** given a question and numbered evidence passages, extract the
  requested metric as JSON (`metric, value, unit, period, evidence, supported`),
  or abstain (`supported=false`) when the evidence does not contain the answer.
  Intended to run behind the Veridoc RAG pipeline (retrieval → extraction).
- **Out of scope / not for:** financial advice; decisions of any consequence;
  reasoning beyond the provided evidence; non-financial text; any real-money use.
  Outputs must be verified against cited sources.

## Limitations & risks

- Small base model + small synthetic dataset → limited robustness and coverage.
- Trained on **fictional, synthetic** statements; not representative of real
  filings (tables, footnotes, scanned PDFs, messy numerics).
- A valid evidence reference proves the citation exists, **not** that it supports
  the claim. Numeric extraction can still err.
- Prompt-injection resistance depends on the base model; measured, not assumed.

## Training

- **Method:** supervised fine-tuning with LoRA (PEFT) on prompt-masked
  completions (JSON targets). Greedy decoding at eval. Deterministic seed.
- **Config:** see `training/veridoc_ft/config.py` (r=16, α=32, dropout=0.05,
  targets = Qwen3 attention+MLP projections) and the committed
  `training_metrics.json` from the run.
- **Compute:** _fill from the run_ (device, VRAM peak, wall-clock).

## Data

- Synthetic, fictional, self-authored (CC0-equivalent); no third-party or
  private data. Categories: answerable, unanswerable/hard-negative, conflicting
  (restated figures), prompt-injection. Split by (company, metric) **family** so
  no template instance leaks across train/test. Version + per-split SHA-256 in
  `data/v1/dataset_card.json`.

## Evaluation

Held-out test set; identical decoding for base and adapter. Metrics: JSON parse
success, schema validity, exact metric/value/unit/period, evidence-reference
validity, abstention precision/recall, injection resistance, latency.

| Metric | Base (Qwen3-0.6B) | + LoRA adapter |
| --- | --- | --- |
| schema_valid | _TBD_ | _TBD_ |
| value_exact | _TBD_ | _TBD_ |
| evidence_ref_valid | _TBD_ | _TBD_ |
| abstention_recall | _TBD_ | _TBD_ |

> **Numbers pending a GPU run.** As of this draft the end-to-end base/adapter
> benchmark on real hardware has **not been run** (see the project Phase 4
> report). Fill from `artifacts/baseline.json` and `artifacts/adapter.json`;
> do not publish without real measurements and 95% CIs.

## How to use (adapter loading)

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = "Qwen/Qwen3-0.6B"
rev = "c1899de289a04d12100db370d81485cdf75e47ca"
tok = AutoTokenizer.from_pretrained(base, revision=rev)
model = AutoModelForCausalLM.from_pretrained(base, revision=rev)
model = PeftModel.from_pretrained(model, "<org>/veridoc-extract-qwen3-0.6b-lora")
# Build the prompt with veridoc_ft.prompt.build_messages(question, evidence)
```

## Reproduction

See `training/README.md` for exact dataset/baseline/train/eval commands. The
dataset is regenerable from a seed; the base revision is pinned.
