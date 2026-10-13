# Publication Report — Phase 5B (awaiting approval)

> **STOP / approval gate.** No public repos created, no artifacts uploaded
> (not even to a private HF repo), no code pushed, no visibility changed.

1. **Proposed GitHub repository:** `<org-or-user>/veridoc-ai` (public).
2. **Proposed Hugging Face repository:** `<org>/veridoc-extract-qwen3-0.6b-lora`
   (model repo; create **private**, flip public only after owner review).
3. **Security scan (final):** no emails/personal identifiers, secrets, tokens,
   SSH/private keys, internal IPs/hostnames, datasets, weights, or `.env` in the
   clean snapshot (172 files) or its single fresh commit. The historical
   personal-email issue is fully avoided because the public snapshot has **no
   upstream Git history**.
4. **Full-stack deployment verification (from the public snapshot):** Docker
   Compose build OK; gateway + web healthy; upload→ingest (6 pages/6 chunks)→
   retrieve (reranked, correct page + citation)→grounded RAG (verified citations)
   all pass; negatives: non-PDF→415, empty query→400, empty question→400,
   unanswerable→abstain. **MOCK MODE clearly identified** (`done.mock=true`;
   UI badge). No real-inference server running locally → real-model smoke **not
   run** (app's real path is config-only); mock never presented as real.
   Code gates on the release commit: JS lint/typecheck + tests (contracts 8 /
   api 18 / web 8); training 35; ai 55 (+14 DB-gated skips); ruff + mypy clean.
5. **Adapter checksum (verified on server):**
   `165518747f28f41e6c8fe5a673988ff58d6f2c90e2b3200085bbd86162b58497`.
6. **Public release file manifest:** full source tree (apps/, services/,
   packages/, training/ code, infra/, docs/, LICENSE, README, CONTRIBUTING) —
   172 tracked files, no weights/data/secrets. HF upload = adapter-only
   (config + safetensors + tokenizer + chat template + model-card README);
   excludes checkpoints, optimizer/trainer state, base weights, data.
7. **Model card & docs:** `training/MODEL_CARD.md` complete with measured
   base/v1/v2 numbers and all mandated caveats (adapter not from scratch;
   templated SEC evidence; frozen benchmark targeted v2 → ≈100% is a regression
   check, not independent generalization; authentic filing-text untested; not
   financial advice). Supporting: EVALUATION, ATTRIBUTIONS, SECURITY, SHOWCASE,
   RELEASE_MANIFEST.
8. **Unresolved blockers:** (a) owner approval required; (b) `<org>` / repo names
   to confirm; (c) HF write token (never committed) + a real `SEC_USER_AGENT`;
   (d) *quality, non-gating for experimental:* authentic filing-text eval and
   end-to-end RAG real-doc eval remain unrun.
9. **Exact publish commands:** see `docs/RELEASE_PUBLICATION.md` (GitHub
   `gh repo create … && git push` from the clean snapshot; HF `create_repo`
   private → `upload_file` card → `upload_folder` adapter-only with explicit
   allow/ignore lists → review → flip public).
