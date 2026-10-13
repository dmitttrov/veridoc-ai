# Veridoc AI — North Star

## Mission

Make financial documents **answerable and verifiable**. Veridoc AI lets a person
ask natural-language questions about publicly shareable financial documents and
receive answers that are grounded in the source text, with explicit document and
page citations — so every claim can be checked against its origin.

## Who it is for

- **Analysts and researchers** who need to extract figures and narrative facts
  from long filings and interim reports without reading every page.
- **Finance and operations teams** comparing reporting periods (e.g. this year
  vs. last) and reconciling line items.
- **Engineering interviewers and prospective clients** evaluating the author's
  ability to build a correct, maintainable, production-oriented AI system.

Veridoc AI is a portfolio and reference project. It is **not** regulated
financial advice and must never be used as the sole basis for a financial
decision.

## What makes it different

1. **Grounded, cited answers.** Responses are tied to retrieved passages with
   document + page provenance. If the evidence is not in the corpus, the system
   says so rather than inventing figures.
2. **Verifiability over fluency.** Correctness and traceability are the headline
   features; the UI foregrounds citations, not just prose.
3. **Reproducible, open engineering.** Every component runs from a fresh
   checkout with documented commands, deterministic mocks, and CI. The planned
   domain-adapted model ships with a model card, evaluation results, and
   reproducible training artifacts.
4. **Honest scope.** We fine-tune an existing open-weight model with LoRA/QLoRA.
   We do **not** claim to train a foundation model from scratch, and we never
   publish fabricated metrics.

## Success criteria

**Phase 1 (this milestone) — vertical slice**

- A user can open the web app, submit a question, and watch a response stream in
  end-to-end (React → NestJS → FastAPI → back), produced by a clearly labelled
  deterministic mock.
- Health endpoints, typed contracts, automated tests, and CI are in place.
- The entire system runs locally with **no GPU and no paid services**.

**Later phases — product**

- Real document ingestion and parsing with page-level provenance.
- Hybrid (lexical + vector) retrieval with reranking, measurably better than a
  single-strategy baseline on a held-out question set.
- Source-grounded generation with faithfulness and citation-accuracy metrics.
- A small domain-adapted model published to Hugging Face with a model card and
  reproducible artifacts.

## Explicit non-goals

- Not a general-purpose chatbot or web search assistant.
- Not regulated financial, investment, legal, or tax advice.
- No ingestion of private, confidential, or personally identifying documents in
  this project's public fixtures or demos.
- No training of a foundation model from scratch.
- No premature distributed infrastructure (Kubernetes, Kafka, service meshes,
  multi-agent orchestration) until a concrete, demonstrated need exists.

## Guiding principles

- **Grounded or silent.** Prefer "I can't find that in the sources" to a
  confident guess.
- **Deterministic where possible.** Mocks and tests are deterministic so
  behavior is reproducible and CI is trustworthy.
- **Typed at every boundary.** Shared contracts, strict TypeScript, strict
  Python typing.
- **Minimal dependencies.** Add infrastructure only when the product needs it.
- **Honest claims.** Never fabricate performance numbers or capabilities.
