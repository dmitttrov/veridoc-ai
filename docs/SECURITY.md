# Veridoc AI — Security Model

Scope: a public, open-source system that answers questions
over **publicly shareable** financial documents. This document states the trust
boundaries and the threats we design against. Items are labelled **[MVP]**
(enforced now) or **[Planned]** (enforced when the relevant feature lands).

## 1. Trust boundaries

```
 Untrusted          │  Public edge (validates)   │  Internal (trusted network)
────────────────────┼────────────────────────────┼────────────────────────────
 Browser / user     │  NestJS gateway (apps/api)  │  FastAPI AI service
 input, uploaded     →  CORS, input validation,    →  inference, retrieval,
 documents          │  timeouts, error shaping    │  (future) DB + model server
```

- **Browser ↔ gateway** is the only publicly exposed boundary. The gateway
  treats all input as untrusted and validates it against the shared zod
  contract before acting. **[MVP]**
- **Gateway ↔ AI service** is an internal, server-to-server hop on a private
  network. The AI service is **never** published to the host or internet; in
  Docker Compose it has no host port mapping. **[MVP]**
- **Uploaded documents** (when added) are untrusted content and a primary
  attack surface. **[Planned]**

## 2. Inference service exposure

- The AI service must not be directly reachable by browsers or the public
  internet. Enforced in Compose by omitting a published port and keeping it on
  the internal network; CORS defaults to empty there. **[MVP]**
- Production deployments must place the AI service on a private subnet/security
  group reachable only from the gateway. **[Planned]**
- No secrets are embedded in images or code; all configuration is via
  environment variables with documented `.env.example` files, and real `.env`
  files are git-ignored. **[MVP]**

## 3. Upload security **(implemented — Phase 2)**

Enforced today across the gateway and the AI service (defense in depth):

- **Type allow-list**: only `application/pdf`, checked at the gateway and
  re-checked in the AI service, plus a **PDF signature** (`%PDF-`) check on the
  bytes themselves. **[MVP]**
- **Size limit** (`AI_MAX_UPLOAD_BYTES`, default 25 MiB) enforced by the gateway
  (multer limit) and again in the AI service by bounded chunked reads; **page
  count limit** (`AI_MAX_PAGES`, default 300). Oversized/too-many-pages uploads
  are rejected early with 413. **[MVP]**
- **Encrypted PDFs are rejected** (no decryption attempted); **malformed PDFs**
  are rejected with a typed error. **[MVP]**
- **Processing timeout** (`AI_PDF_PARSE_TIMEOUT_S`) bounds CPU time for parsing/
  extraction (runs in a worker thread under `asyncio.wait_for`). **[MVP]**
- **Generated IDs only**: documents/pages/chunks use deterministic UUIDs derived
  from the content hash; the original filename is stored as metadata but never
  used as a filesystem path (no path traversal; uploads are not written to
  disk). **[MVP]**
- **No execution of document content**: extracted text is treated purely as data
  — parsed, normalized, chunked, embedded, stored. It is never eval'd,
  interpreted, or used to drive control flow. **[MVP]**
- **Content is never logged**: logs record only metadata (filename, hash prefix,
  counts, error codes), never extracted text. **[MVP]**
- Still assumes uploads are **publicly shareable** and non-sensitive; explicit
  per-user consent UX and antivirus scanning remain future hardening.

## 4. Prompt injection & content risks **(implemented — Phase 3)**

Retrieved document text is **untrusted** and may contain adversarial
instructions ("ignore previous instructions…").

- **Instruction/data separation:** retrieved passages are assembled into a
  clearly delimited EVIDENCE region with `[E1]…` markers; the system prompt
  states the evidence is untrusted data to analyze and that embedded
  instructions must never be followed. **[Built]**
- **Grounded-or-abstain:** the model answers only from provided passages and
  emits a fixed abstention sentinel when evidence is insufficient; empty
  retrieval abstains without calling the model. **[Built]**
- **Output is not executed:** answers are rendered as text; document content
  never drives tool-calling or code execution.
- **Citation verification:** emitted citation markers are mapped back to the
  retrieved chunk set; fabricated references are stripped and counted. Valid
  citations carry a chunk id + character span traceable to stored page text.
  **Validity is not support** — a valid citation proves the reference exists,
  not that it substantiates the claim; this is stated in the UI and docs.
  **[Built]**
- **Verify-then-stream:** the model response is fully generated and its
  citations verified before any token is streamed to the client, so unverified
  or fabricated-citation content is never presented as a final answer. **[Built]**
- **No secret/content logging:** the inference provider never logs prompts,
  document content, API keys, or model responses — only coarse status codes.
  **[Built]**
- Every streamed event is schema-validated on both ends. **[Built]**
- Remaining: injection resistance ultimately depends on the chosen model;
  measured injection resistance is tracked in EVALUATION.md (the mock is trivially
  resistant; a real model must be re-measured). **[Ongoing]**

## 5. Document privacy

- The project handles only **publicly shareable** documents. No real financial,
  personal, or confidential documents appear in fixtures, tests, or demos; all
  fixtures are explicitly fictional. **[MVP]**
- Uploaded documents, model weights, datasets, and generated artifacts are
  git-ignored and never committed. **[MVP]**
- Multi-tenant isolation and per-user access control are **out of scope** for
  the MVP and would require authentication + row-level authorization
  before any non-public use. **[Planned / non-goal for MVP]**

## 6. Transport, CORS, and headers

- CORS on the gateway is restricted to the configured web origin
  (`WEB_ORIGIN`), limited to the methods used. **[MVP]**
- TLS termination is expected at the deployment edge (reverse proxy / platform);
  local development uses plain HTTP on loopback. **[Planned for deploy]**
- Security headers, rate limiting, and request-size caps at the edge are
  planned for Day 14 hardening. **[Planned]**

## 7. Dependencies & supply chain

- Dependencies are kept minimal. The JS workspaces commit a lockfile
  (`package-lock.json`); the deployable AI service commits a hash-pinned Python
  lockfile (`services/ai/requirements.lock` / `requirements-dev.lock`, installed
  with `pip --require-hashes` in CI and the image). The `training/` package
  stays range-pinned in `pyproject.toml` — its torch/CUDA dependency matrix is
  not portably hash-lockable, so exact resolved versions are instead recorded in
  the run manifest at train time — and the base model + its revision are pinned.
  All Docker base images are pinned by `@sha256` digest. **[MVP]**
- CI runs lint, type checks, and tests on every change, builds the container
  images and scans them with Trivy (fails on HIGH/CRITICAL), and Dependabot
  tracks npm, pip, and GitHub Actions updates. **[Built]**

## 8. Denial of service

- The gateway applies upstream timeouts and propagates client disconnects to
  abort in-flight inference, bounding resource use per request, and enforces
  per-IP rate limiting at the edge. **[MVP]**
- Ingestion is concurrency-capped (excess uploads get 429, not queued); PDF
  parsing of untrusted input runs in a **killable child process** under a
  wall-clock timeout so a pathological file cannot pin a CPU, and buffered RAG
  answers are size-bounded. **[Built]**
- Global, cross-instance rate limiting / quotas (shared store) remain a
  hardening item. **[Planned]**

## 9. Explicit non-goals (MVP)

Authentication/authorization, multi-tenancy, handling of sensitive or regulated
documents, and adversarial red-teaming of a real model. These are acknowledged
and deferred; none should be assumed present.

## 10. Reporting

This is a reference project, not a hosted service. Security issues can be raised
via a GitHub issue (once published) describing the concern and reproduction.
