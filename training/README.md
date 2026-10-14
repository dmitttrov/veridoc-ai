# Veridoc AI — Fine-tuning (Phase 4)

Reproducible **LoRA** supervised fine-tuning of a small open-weight base model
for **structured financial-fact extraction from retrieved evidence**. Retrieval
lives in `services/ai`; this package only produces and evaluates the model
artifact. **Nothing is uploaded or published.**

- **Base model:** `Qwen/Qwen3-0.6B` @ revision
  `c1899de289a04d12100db370d81485cdf75e47ca` (Apache-2.0). See
  `docs/MODEL_STRATEGY.md` / ADR-0021.
- **Not fine-tuned from scratch** — this is a PEFT/LoRA adapter over the base.
- Training data, checkpoints, and adapters are **git-ignored** (`data/`,
  `artifacts/`).

## Environment

```bash
cd training
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"                            # CPU
# GPU: install a CUDA build of torch matching your driver first, then:
# pip install -e ".[dev]"            (+ ".[qlora]" on Linux/CUDA for 4-bit)
```

## Pipeline (exact commands)

```bash
# 1. Build the dataset (deterministic; writes data/v1 + dataset_card.json with hashes)
python -m veridoc_ft.dataset --out data/v1 --seed 20240601

# 2. Baseline — unmodified base model on the held-out test set (RECORD FIRST)
python -m veridoc_ft.evaluate --data-dir data/v1 --split test \
    --out artifacts/baseline.json

# 3. LoRA fine-tune (full run). Start with a pilot: --max-steps 20
python -m veridoc_ft.train --data-dir data/v1 --output-dir artifacts/adapter-v1

# 4. Adapter — same test set, same decoding
python -m veridoc_ft.evaluate --data-dir data/v1 --split test \
    --adapter artifacts/adapter-v1 --out artifacts/adapter.json

# 5. Compare (deltas + Wilson 95% CIs)
python -c "import json;from veridoc_ft.evaluate import compare;\
print(json.dumps(compare(json.load(open('artifacts/baseline.json')),json.load(open('artifacts/adapter.json'))),indent=2))"
```

## Real-world evaluation (Phase 4C)

A real extraction benchmark is built from **SEC EDGAR XBRL** (authoritative,
public-domain) — exact values/units/periods tied to real 10-K filings. Ground
truth is never model-generated or typed from memory.

```bash
# Build the real test set (fetches SEC XBRL; data/ is git-ignored)
python -m veridoc_ft.realeval.dataset --out data/realeval --built-at <date>

# Oracle evaluation (correct passage provided; isolates extraction from retrieval)
python -m veridoc_ft.realeval.evaluate --data data/realeval/real_test.jsonl \
    --out artifacts/real_base.json                                  # base
python -m veridoc_ft.realeval.evaluate --data data/realeval/real_test.jsonl \
    --adapter artifacts/adapter-v1 --out artifacts/real_adapter.json  # adapter
python scripts/report.py --baseline artifacts/real_base.json \
    --adapter artifacts/real_adapter.json --out artifacts/real_comparison.json
```

Value comparison uses `veridoc_ft.realeval.normalize` (currency, commas,
millions/billions, parentheses-negatives). Citation *validity* and *support* are
scored separately. See `docs/EVALUATION.md` for status (the measured run is
pending GPU-server access).

## Tests

```bash
pytest                         # CPU training smoke + normalizer + real-eval scorer
ruff check . && mypy veridoc_ft
```

## Hardware

- **CPU**: smoke tests + tiny pilots only (0.6B inference is slow but works).
- **GPU (recommended)**: a bf16-capable card (Ampere+ / compute ≥ 8.0) with
  **≥ 16 GB VRAM** for comfortable full-precision LoRA, or **≥ 8 GB** with
  4-bit **QLoRA** (`.[qlora]`, Linux/CUDA). bf16 is preferred; fp16 is used on
  pre-Ampere CUDA automatically.
- The local dev GPU here (GTX 1650 Ti, 4 GB, Turing, driver 462.30) is **not
  suitable**: no bf16, 4 GB is too small, and the toolchain is CPU-only. GPU
  runs should target a machine meeting the above.

## Serving the adapter (RAG integration)

The runtime AI service (`services/ai`) already talks to any OpenAI-compatible
server via `AI_INFERENCE_PROVIDER=openai_compatible` + `AI_INFERENCE_BASE_URL` +
`AI_INFERENCE_MODEL` (ADR-0019). Switching between **mock**, **base**, and
**adapter** is an explicit configuration change — the service never switches
models silently.

Base vs. adapter are served as distinct model names by a local vLLM server:

```bash
# Base model
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-0.6B --revision c1899de289a04d12100db370d81485cdf75e47ca \
  --port 8001
#   services/ai: AI_INFERENCE_PROVIDER=openai_compatible
#                AI_INFERENCE_BASE_URL=http://localhost:8001/v1
#                AI_INFERENCE_MODEL=Qwen/Qwen3-0.6B

# Base + LoRA adapter (served as a separate model id)
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-0.6B --revision c1899de289a04d12100db370d81485cdf75e47ca \
  --enable-lora --lora-modules veridoc-extract=artifacts/adapter-v1 --port 8001
#   services/ai: AI_INFERENCE_MODEL=veridoc-extract   (select the adapter)
```

For local evaluation without a server, `veridoc_ft.infer.load_model(config,
adapter_path=...)` loads base or base+adapter directly (same decoding), and
`veridoc_ft.evaluate` validates that generations are schema-conformant.

The **mock** provider remains the default and keeps Phase 1–3 working with no
model server.

See `MODEL_CARD.md` for the draft Hugging Face card.
