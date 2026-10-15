# Attributions & License Audit

Veridoc AI is licensed **Apache-2.0** (see `LICENSE`). This file records the
third-party components it uses and their licenses. Audited at Phase 5A by
scanning installed package metadata/classifiers for copyleft licenses — **none
found** (no GPL / AGPL / LGPL anywhere; PyMuPDF/AGPL is deliberately NOT used).

## Models (not redistributed by this project)

| Component | ID / revision | License | Notes |
| --- | --- | --- | --- |
| Base model | `Qwen/Qwen3-0.6B` @ `c1899de289a04d12100db370d81485cdf75e47ca` | **Apache-2.0** | Base weights are **not** redistributed. We publish only a LoRA **adapter**; the base is downloaded by the user from Hugging Face. Attribution to Qwen. |
| Embedding (optional) | `sentence-transformers/all-MiniLM-L6-v2` | Apache-2.0 | Optional; default retrieval uses a dependency-free deterministic provider. |
| Reranker (optional) | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Apache-2.0 | Optional second-stage reranker. |

The Qwen3 base is Apache-2.0, which permits fine-tuning and redistribution of a
derived **LoRA adapter** with attribution. We do not redistribute base weights.

## Key Python dependencies

| Package | License |
| --- | --- |
| torch | BSD-3-Clause |
| transformers, peft, accelerate, datasets, safetensors, tokenizers | Apache-2.0 |
| numpy, scipy | BSD-3-Clause |
| fastapi, pydantic, pydantic-settings, pgvector(-python) | MIT |
| starlette, uvicorn, httpx, reportlab | BSD |
| asyncpg, python-multipart | Apache-2.0 |
| **pypdf** (PDF parsing) | **BSD-3-Clause** (chosen over AGPL PyMuPDF — ADR-0010) |
| certifi | MPL-2.0 (file-level copyleft; redistribution-compatible) |

## Key JavaScript dependencies

| Package | License |
| --- | --- |
| react, react-dom, vite, @vitejs/plugin-react | MIT |
| @nestjs/* , express, multer, rxjs, zod | MIT |
| typescript | Apache-2.0 |
| vitest, jest, eslint, @testing-library/* | MIT |

## Data & benchmarks

| Material | Source | License / status |
| --- | --- | --- |
| Synthetic training/eval corpora (v1, v2) | Self-authored, fictional | CC0-1.0 (public domain dedication) |
| Real benchmark ground truth | **SEC EDGAR XBRL** (`data.sec.gov`) | US government work — **public domain**, redistributable. SEC requires a descriptive `SEC_USER_AGENT`. |

Benchmark evidence passages are **templated prose that embed real SEC XBRL
values** — they are not verbatim filing excerpts (see `docs/EVALUATION.md`).

## Redistribution restrictions

- **Do not redistribute the Qwen3 base weights** — publish the adapter only, with
  attribution; users fetch the base from Hugging Face.
- SEC data is public domain; no restriction, but set `SEC_USER_AGENT` to your own
  contact per SEC's fair-access policy.
- No other third-party redistribution restrictions apply.
