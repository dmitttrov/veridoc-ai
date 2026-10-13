# Veridoc AI — Model Strategy

How Veridoc AI approaches language-model capability: honestly, reproducibly, and
with evaluation. **No model has been trained or published yet.** This document
is the plan and the guardrails; it will be updated with real results (never
fabricated) as work lands.

## 1. Honest framing

- We will **fine-tune an existing open-weight model** using parameter-efficient
  methods (LoRA/QLoRA). We will **not** claim to have pretrained a foundation
  model from scratch.
- We will never publish fabricated benchmark numbers. Every metric in this repo
  is produced by a committed, re-runnable script over a committed evaluation set.
- Until a real model is wired in, the system runs a clearly labelled
  deterministic mock (see `ARCHITECTURE.md`, `DECISIONS.md` ADR-0005).

## 2. Serving architecture (capability seam)

Generation sits behind the `InferenceProvider` protocol in `services/ai`:

- **MVP:** `MockProvider` (deterministic; default; used by CI).
- **Next:** `OpenAICompatibleProvider` targeting a configurable base URL — first
  any local OpenAI-compatible server for development, then a **vLLM** server
  hosting our base model + LoRA adapter.

Because vLLM exposes an OpenAI-compatible API, the same provider works for a
hosted dev endpoint and our self-hosted model, keeping GPU concerns isolated
behind one seam. The mock remains the CI/default backend so tests never need a
GPU.

## 3. Base model — SELECTED (Phase 4): Qwen3-0.6B

**Decision:** `Qwen/Qwen3-0.6B`, pinned revision
`c1899de289a04d12100db370d81485cdf75e47ca`. Recorded as ADR-0021.

Verified from the model's Hugging Face page + API:

| Property | Value |
| --- | --- |
| Model id / revision | `Qwen/Qwen3-0.6B` @ `c1899de289a04d12100db370d81485cdf75e47ca` |
| License | **Apache-2.0** — permits fine-tuning and redistribution of a LoRA adapter with attribution |
| Architecture | `Qwen3ForCausalLM`, 28 layers, GQA (16 Q / 8 KV heads), 0.6B params (0.44B non-embedding) |
| Context length | 32,768 tokens |
| Tokenizer / chat | Qwen3 tokenizer with instruction chat template; `enable_thinking` toggle (we use `False` for direct JSON) |
| Tooling | `transformers>=4.51` (we run 4.57.6), PEFT, and vLLM all support Qwen3 |
| Hardware | tiny: fits CPU for smoke/pilot; a bf16 GPU (Ampere+) with ≥8–16 GB is comfortable for LoRA |

**Why this model:** smallest credible modern instruction model with a permissive
license and first-class tooling — ideal for a *controlled, reproducible*
adapter experiment on modest hardware. We do **not** claim it was trained from
scratch; we fine-tune it with LoRA.

Rejected for the initial experiment (kept as future options): Llama 3.x
(community license nuances), Qwen2.5, Mistral 7B, Phi-3.x mini — all larger and
unnecessary for a controlled first adapter.

## 4. Adapter training approach

- **Method:** LoRA, and QLoRA (4-bit base) when VRAM-constrained, via the PEFT
  ecosystem. Only adapter weights are produced and shipped — small and cheap to
  host and distribute.
- **Task framing:** supervised fine-tuning for *source-grounded financial QA* —
  given a question and retrieved passages, produce a grounded answer with
  citations, and abstain when evidence is absent.
- **Reproducibility:** a pinned training script with fixed seeds, logged
  hyperparameters, and recorded base-model revision. Configs are committed;
  weights, datasets, and checkpoints are **git-ignored** and never committed.

## 5. Dataset provenance (strict)

- **Only** permissively licensed or public-domain sources, and **synthetic**
  data we generate ourselves. Provenance and license for every source are
  documented before use.
- **No** scraping of paywalled/copyrighted filings into training data; **no**
  real personal or confidential documents; **no** datasets with unclear terms.
- Synthetic SFT examples (question, passages, grounded answer, citations) are
  generated from public or fictional documents, with a documented generation
  procedure and quality checks. Any model-assisted data generation respects the
  generating model's terms.
- A `DATA_CARD` will accompany the dataset describing composition, generation
  method, and known limitations/biases.

## 6. Evaluation (before any claims)

Evaluated on a committed, held-out set with re-runnable scripts:

- **Retrieval:** recall@k / MRR (hybrid vs. lexical-only vs. vector-only).
- **Answer faithfulness:** is every claim supported by the cited passages?
- **Citation accuracy:** precision/recall of cited spans vs. gold spans.
- **Abstention:** correct refusal rate when the answer is not in context.
- **Base vs. fine-tuned:** the same harness run on both, reported side by side,
  including regressions. Results are committed as generated.

## 7. Hugging Face release strategy (not yet executed)

When quality justifies it and only after explicit approval:

- Publish the **LoRA adapter** (not full weights unless license requires/permits)
  with a complete **model card**: intended use, out-of-scope use, base model +
  revision, training data provenance and license, training procedure and
  hyperparameters, evaluation methodology and honest results, and limitations
  (including that this is not financial advice).
- Include the reproducible training config and eval scripts, and a pinned
  environment, so results can be independently reproduced.
- Respect the base model's license and naming/attribution requirements.

## 8. Risks & limitations

- Small models may hallucinate or mis-cite; grounded-or-abstain prompting,
  retrieval quality, and citation verification are the primary mitigations.
- Financial text is precise; numeric extraction errors are high-impact — hence
  the emphasis on faithfulness and citation metrics over fluency.
- Fine-tuning on synthetic data can bake in generator biases; the data card and
  held-out human-checked eval guard against overfitting to synthetic artifacts.

## 9. Status

| Item | Status |
| --- | --- |
| Provider abstraction + mock | **Done** |
| OpenAI-compatible / vLLM provider | Planned (Days 8–9) |
| Base model selection (ADR) | Not started |
| Dataset + data card | Not started |
| Evaluation harness | Planned (Days 10–11) |
| LoRA/QLoRA training | Planned (Days 12–13) |
| Hugging Face publication | Not started — requires explicit approval |
