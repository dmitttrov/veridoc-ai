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
  completions (JSON targets). Greedy decoding at eval. Deterministic seed=42.
- **Config:** r=16, α=32, dropout=0.05, targets = Qwen3 attention+MLP
  projections; lr 2e-4, 3 epochs, batch 1 × grad-accum 16, bf16, gradient
  checkpointing. 186 train / 60 val examples, 36 optimizer steps.
- **Compute (measured):** 1× NVIDIA RTX PRO 6000 Blackwell (96 GB); training
  wall-clock **92.9 s**, **peak 2.23 GB** VRAM; adapter **39 MB**. Final train
  loss 0.18 (curve 1.14→0.0003), validation loss 0.0014. torch 2.11.0+cu128.

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

Measured on 1× RTX PRO 6000 Blackwell, greedy decoding, n=42 held-out test.

| Metric | Base (Qwen3-0.6B) | + LoRA adapter | Paired Δ (95% CI) |
| --- | --- | --- | --- |
| JSON parse success | 1.000 | 1.000 | — |
| schema_valid | 0.714 | 1.000 | +0.286 [0.167, 0.429] ✓ |
| value_exact (n=28 supported) | 0.750 | 1.000 | +0.250 [0.107, 0.429] ✓ |
| metric_exact | 0.750 | 1.000 | +0.250 [0.107, 0.429] ✓ |
| unit_correct | 0.750 | 1.000 | — |
| period_correct | 1.000 | 1.000 | — |
| evidence_ref_valid | 1.000 | 1.000 | 0.000 [0,0] |
| abstention precision / recall | 1.00 / 0.857 | 1.00 / 1.00 | — |
| injection_resistance | 1.000 | 1.000 | — |
| mean latency (greedy) | 0.99 s | 1.12 s | — |

"✓" = paired-bootstrap 95% CI of the per-example difference excludes 0 (credible
improvement). Per-category, the gains come from **conflicting** (restated-figure)
value extraction (0/7 → 7/7) and **schema-valid abstention** on unanswerable
items (2/14 → 14/14 schema-valid).

> ⚠️ **Synthetic-benchmark result — NOT real-document performance.** The dataset
> is small (186/60/42), fictional, and **templated**; the adapter fit it almost
> perfectly (val loss ~0.001), so these near-ceiling numbers chiefly show the
> model learned the dataset's output conventions. They do **not** measure
> performance on real financial filings (tables, footnotes, OCR, messy numerics)
> and must not be presented as such. Treat as a controlled proof-of-pipeline.

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
