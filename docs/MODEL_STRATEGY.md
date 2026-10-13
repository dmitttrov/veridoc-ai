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

## 3. Candidate base models (to be finalized)

Selection criteria: permissive/commercial-friendly license, strong instruction
following at a **small** size (roughly 1B–8B so it fits modest GPUs with QLoRA),
good long-context handling for document passages, and active tooling support.

Candidate families under consideration (final choice recorded as an ADR once
license and eval checks pass):

- Llama 3.x Instruct (8B / smaller variants)
- Qwen2.5 Instruct (1.5B / 7B)
- Mistral 7B Instruct
- Phi-3.x mini/small

Non-negotiables before selection: confirm the license permits our intended use
and redistribution of a LoRA adapter, and that the model card allows derivative
fine-tunes.

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
