# Veridoc AI — Showcase

Presentation material for the public experimental release. All claims are backed
by committed, re-runnable code and measured results (`docs/EVALUATION.md`).

## One-line

A **domain-adapted LoRA model** (`Qwen/Qwen3-0.6B`) for structured financial-fact
extraction, integrated into a **full-stack, source-grounded RAG application**.

## Technical case study (short)

**Problem.** Extract financial facts from documents *verifiably* — every answer
tied to its evidence, with the model abstaining when evidence is absent.

**System.** React + TypeScript UI → NestJS gateway (SSE, zod validation) →
FastAPI AI service. PDFs are ingested (pypdf, deterministic normalization +
chunking, page-level provenance) into PostgreSQL + pgvector. Retrieval is
**hybrid** (Postgres full-text + pgvector cosine, exact at this scale) fused with
**Reciprocal Rank Fusion**, with an optional cross-encoder reranker. Generation
is **grounded**: retrieved passages are framed as untrusted data, the model
cites evidence markers, citations are **verified** against the retrieval set
(fabricated references rejected), and the answer is **verify-then-streamed**.
A deterministic **mock** provider keeps the whole app runnable with no GPU; a
real OpenAI-compatible/vLLM provider is a config switch (never a silent one).

**Model.** A LoRA adapter (r=16) over a *pinned* Qwen3-0.6B, trained on a
synthetic, schema-constrained extraction dataset. Evaluated base-vs-adapter with
**paired bootstrap** CIs on a frozen 239-example benchmark whose ground truth is
authoritative **SEC EDGAR XBRL**. v1 revealed two weaknesses (negative values,
near-synonym metric confusion); **v2 targeted them** and fixed both (signed
values 3/3; near-synonym abstention 12/12) with no regressions.

**Engineering rigor.** Strict typing (TS strict, Python ruff+mypy), per-package
tests incl. a no-network CPU training smoke test, a pre-model benchmark
integrity audit (caught 2 real data bugs before any model saw the data), Docker
Compose, CI, and honest documentation of every limitation.

> **Honesty note (important).** The benchmark evidence is *templated prose
> containing real SEC figures*, and the frozen benchmark was used to find v1
> weaknesses then targeted in v2 training — so v2's ≈100% scores are a
> **regression check, not independent generalization**. Authentic filing-text
> generalization is **untested**. The model is **experimental** and not for
> financial advice.

## CV-ready description

> **Veridoc AI — full-stack RAG + domain-adapted LLM (open source).** Built an
> end-to-end financial-document intelligence system: React/TypeScript +
> NestJS + FastAPI, PostgreSQL/pgvector hybrid retrieval with RRF and
> cross-encoder reranking, and grounded generation with verified citations and
> abstention. Fine-tuned a Qwen3-0.6B **LoRA** adapter for structured extraction;
> evaluated base-vs-adapter with paired-bootstrap confidence intervals against an
> SEC-XBRL-grounded benchmark; iterated v1→v2 to fix measured failure modes with
> no regressions. Emphasis on reproducibility, strict typing, CI, security/
> license auditing, and rigorously honest evaluation.

## Tech stack

- **Frontend:** React 18, TypeScript (strict), Vite, Vitest.
- **Gateway:** NestJS, zod contracts, SSE streaming, Jest.
- **AI service:** Python 3.11, FastAPI, Pydantic v2, asyncpg; pypdf (BSD).
- **Retrieval:** PostgreSQL + pgvector; FTS + vector + RRF; optional cross-encoder.
- **Model/training:** PyTorch, Transformers, PEFT (LoRA); SEC EDGAR XBRL eval.
- **Infra:** Docker Compose, GitHub Actions CI.

## Screenshots / demo

No hosted demo (nothing is deployed). Run locally:
`docker compose -f infra/docker-compose.yml up --build` → <http://localhost:5173>.
To capture screenshots: (1) the **Grounded Answer** tab after asking a question
(answer + cited sources + mock/real badge); (2) the **Retrieval** tab showing
ranked passages with scores; (3) the document upload + ingestion status.

## Hugging Face model

Adapter (experimental): **`<org>/veridoc-extract-qwen3-0.6b-lora`** *(placeholder
— not yet published; see `docs/RELEASE_PUBLICATION.md`)*.

## Reproducibility

- App: `docker compose -f infra/docker-compose.yml up --build`.
- Model: `training/README.md` (build dataset → baseline → train → evaluate →
  compare). Base revision pinned; datasets regenerate deterministically from a
  seed; adapter checksum in `docs/RELEASE_MANIFEST.md`.

## 90-second demo script

1. **(0:00–0:15)** "Veridoc AI answers questions about financial documents with
   *verifiable* citations — and a LoRA-fine-tuned extractor." Show the README
   experimental disclaimer.
2. **(0:15–0:35)** `docker compose … up`; open the app. Upload a sample PDF;
   point out the ingestion status (parsed → chunked → embedded, page provenance).
3. **(0:35–0:55)** **Retrieval** tab: ask "What was total revenue?"; show ranked
   passages with lexical/semantic/fused (and rerank) scores and page citations.
4. **(0:55–1:15)** **Grounded Answer** tab: ask again; show the streamed answer
   with inline cited sources and the **MOCK MODE** badge; note citations are
   verified and fabricated references are rejected; show an *abstention* on an
   unanswerable question.
5. **(1:15–1:30)** Switch to the model: show `docs/EVALUATION.md` base→v1→v2
   table and the honesty caveat (templated evidence, targeted benchmark,
   authentic-text untested). Close: "experimental, reproducible, honestly
   measured."
