# Release Manifest — Veridoc AI (Phase 5A, experimental)

Prepared for a public experimental release. **Not published.** Generated/verified
during Phase 5A; see `docs/EVALUATION.md` for methodology and measured results.

## Provenance & integrity

| Item | Value |
| --- | --- |
| Private source commit (release baseline) | `edf6743` (Phase 5B; snapshot cut from here via `git archive`) |
| Public snapshot | fresh single commit, **no upstream history** (see docs/RELEASE_PUBLICATION.md) |
| Base model | `Qwen/Qwen3-0.6B` |
| Base revision (pinned) | `c1899de289a04d12100db370d81485cdf75e47ca` |
| Adapter **v2** (preferred) SHA-256 | `165518747f28f41e6c8fe5a673988ff58d6f2c90e2b3200085bbd86162b58497` |
| Adapter v1 (superseded, immutable) SHA-256 | `c9a492bd1c44667aa2d1420f6644ea53f74955f135be67b623ba6a8fcc26bb67` |
| Adapter size / type | 39 MB / LoRA (r=16, α=32, dropout=0.05) |
| Training dataset v2 hashes | test `d72e98b5…493c`, train `8a0597ec…e893`, val `e067…cadc` |
| Training dataset v1 hashes | test `e3f80775…22f6` (unchanged) |
| Frozen SEC benchmark SHA-256 | `9f9c3495b54179b2ca18fe3eeca49c3e3b28c2b93ed1e40735310aa5ca369b65` (239 examples) |
| Evaluation / training code | `training/veridoc_ft/` at the release commit |

Clean-room (fresh venv, committed files only) reproduced: committed tests 35/35,
dataset-v2 hash match, adapter-v2 checksum match, representative extraction
schema-valid.

## Pinned dependency versions (GPU training/eval env)

| Package | Version |
| --- | --- |
| python | 3.12 (server) / 3.11+ supported |
| torch | 2.11.0+cu128 (CUDA 12.8; Blackwell) |
| transformers | 4.57.6 |
| peft | 0.17.1 |
| accelerate | 1.15.0 |
| datasets | 3.6.0 |
| safetensors | 0.8.0 |
| pydantic | 2.14.1 |
| numpy | 2.5.4 |
| node (JS workspaces) | 20+ (dev used 24.3.0) |

## Measured results (summary)

Frozen 239-example SEC benchmark (greedy, identical settings), base → v1 → v2:
schema_valid 0.778→1.0→1.0; value_exact 0.920→0.980→1.0; metric_exact
0.801→0.841→1.0; abstention recall 0.602→0.864→1.0. Paired bootstrap: base→v2
credible on schema/value/metric. v2 fixes v1's signed-value (3/3) and
near-synonym abstention (12/12) weaknesses with no regressions.

## Known limitations (must ship with the release)

1. **Fine-tuned (LoRA) adapter, not trained from scratch**; base is Qwen3-0.6B.
2. **Benchmark evidence is templated prose wrapping real SEC XBRL figures** — not
   verbatim filing text.
3. The frozen benchmark was used to find v1 weaknesses that were then **targeted
   in v2 training**; v2's ≈100% frozen scores are a **regression check, not
   independent generalization**.
4. **Authentic filing-text generalization is untested** (real 10-K/10-Q prose,
   tables, footnotes). Primary blocker for a non-experimental release.
5. Small base model + small synthetic training set; **experimental**, **not for
   financial advice** or unsupervised high-stakes use.
6. End-to-end RAG real-document evaluation not yet run.

## Publication status

See `docs/RELEASE_PUBLICATION.md`. **Blocker:** personal email in 3 historical
commits (fixed forward; history scrub or clean-snapshot required before a public
GitHub push). Hugging Face release is **adapter-only**; base weights are never
uploaded. All steps require explicit owner approval.
