# Hugging Face Release Checklist (Veridoc Extract LoRA) — NOT YET PUBLISHED

Do not publish until every box is checked and explicitly approved by the owner.
Phase 4B ran the first GPU training; Phase 4C.1 ran the real-world evaluation
(decision: **A — experimental release justified**, with documented limits).
An *experimental*, clearly-labelled adapter release is justified; a
*non-experimental* release still needs authentic filing-text evaluation.

## Evidence & correctness
- [x] GPU run completed on 1× RTX PRO 6000 Blackwell; baseline/adapter/comparison
      reports generated (kept on the server, out of Git).
- [x] Adapter shows a **credible paired** improvement on the synthetic benchmark
      (paired-bootstrap 95% CI of the per-example diff excludes 0 for
      schema_valid, value_exact, metric_exact).
- [x] Per-category deltas reviewed (gains: conflicting, schema-valid abstention).
- [x] Latency and peak VRAM recorded (train peak 2.23 GB; infer peak ~1.3 GB).
- [x] **Real-world evaluation EXECUTED (Phase 4C.1).** 239-example SEC XBRL
      benchmark; pre-model audit cross-checked 151/151 gold values against
      authoritative XBRL. Adapter shows **credible paired** improvement on REAL
      values: schema_valid 0.778→1.0, value_exact 0.920→0.980, metric_exact
      0.801→0.841 (all paired-bootstrap CI excludes 0). → generalizes, not just
      memorizes. **Decision: A — experimental release justified.**
- [x] Regressions preserved and documented: negative/parenthesized values
      (adapter worse than base); abstention gap on near-synonym metrics.
- [ ] **BLOCKER for NON-experimental release:** authentic filing-TEXT evaluation.
      The 239 examples use templated prose around real XBRL figures — authentic
      10-K/10-Q text (tables, footnotes, prose) generalization is **untested**.
- [ ] End-to-end RAG real-eval (retrieval + extraction) over ingested real
      documents (needs the services/ai stack) — not yet run.

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
