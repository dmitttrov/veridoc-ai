# Hugging Face Release Checklist (Veridoc Extract LoRA) — NOT YET PUBLISHED

Do not publish until every box is checked and explicitly approved by the owner.
Phase 4B executed the first real GPU run; boxes it satisfied are checked.

## Evidence & correctness
- [x] GPU run completed on 1× RTX PRO 6000 Blackwell; baseline/adapter/comparison
      reports generated (kept on the server, out of Git).
- [x] Adapter shows a **credible paired** improvement on the synthetic benchmark
      (paired-bootstrap 95% CI of the per-example diff excludes 0 for
      schema_valid, value_exact, metric_exact).
- [x] Per-category deltas reviewed (gains: conflicting, schema-valid abstention).
- [x] Latency and peak VRAM recorded (train peak 2.23 GB; infer peak ~1.3 GB).
- [ ] **BLOCKER: real financial-document evaluation.** Current numbers are on
      templated synthetic data only and must not be presented as real-filing
      performance. A real-document eval set is required before release.

## Model card
- [x] `MODEL_CARD.md` metric tables filled with **measured** numbers + paired CIs.
- [x] Compute section filled (device, VRAM, duration).
- [x] Intended use / out-of-scope / limitations reviewed; synthetic caveat added.
- [x] "Not financial advice", "not fine-tuned from scratch", "adapter only".

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
