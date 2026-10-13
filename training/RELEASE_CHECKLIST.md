# Hugging Face Release Checklist (Veridoc Extract LoRA) — NOT YET EXECUTED

Do not publish until every box is checked and explicitly approved by the owner.

## Evidence & correctness
- [ ] GPU (or sufficient) run completed; `artifacts/baseline.json` and
      `artifacts/adapter.json` committed-as-generated (never hand-edited).
- [ ] Adapter shows a **credible** improvement over base (non-overlapping 95%
      CIs on at least the headline metric) OR the card honestly reports no/mixed
      improvement.
- [ ] Per-category deltas and failure examples reviewed.
- [ ] Latency and peak VRAM recorded.

## Model card
- [ ] `MODEL_CARD.md` metric tables filled with **measured** numbers + CIs.
- [ ] Compute section filled (device, VRAM, duration).
- [ ] Intended use / out-of-scope / limitations reviewed.
- [ ] "Not financial advice", "not fine-tuned from scratch", "adapter only".

## Data & licensing
- [ ] `dataset_card.json` provenance/license accurate; data is synthetic only.
- [ ] No private/third-party/copyrighted data in training or examples.
- [ ] Base model Apache-2.0 attribution to Qwen present; base NOT redistributed.
- [ ] Adapter license (Apache-2.0) stated.

## Artifacts & hygiene
- [ ] Only the **adapter** (+ card + config) is uploaded; no base weights.
- [ ] No datasets, checkpoints, logs, credentials, or tokens in the repo/upload.
- [ ] Pinned base revision and dependency versions documented.
- [ ] Reproduction commands verified from a clean checkout.

## Publication (only after approval)
- [ ] Create the HF repo; upload adapter + card.
- [ ] Add a loading example and link back to the project.
- [ ] Tag the git commit used for the release.
