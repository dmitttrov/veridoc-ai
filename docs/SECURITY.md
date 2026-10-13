# Veridoc AI — Security Model

Scope: a public, open-source, portfolio-grade system that answers questions
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

## 3. Upload security *(Planned — Days 2–3)*

When document upload lands, the gateway will enforce, before any processing:

- **Type allow-list** (e.g. PDF) by content sniffing, not just extension.
- **Size limits** and a maximum page count; reject oversized payloads early.
- **Filename sanitization**; store under generated IDs, never user-supplied
  paths (defends against path traversal).
- **No execution / no macro evaluation**; parse in a constrained library.
- Parsing in an isolated worker with CPU/memory/time limits to bound
  decompression-bomb and malformed-file risks.
- Clear user consent that uploads are **publicly shareable** and non-sensitive.

## 4. Prompt injection & content risks *(Planned, with MVP groundwork)*

Retrieved document text is **untrusted** and may contain adversarial
instructions ("ignore previous instructions…").

- **Instruction/data separation:** retrieved passages are placed in a clearly
  delimited data region; the system prompt states that document content is data
  to be analyzed, never instructions to follow. **[Planned]**
- **Grounded-or-abstain:** the model must answer only from provided passages and
  say so when evidence is absent; this both improves faithfulness and limits
  injection leverage. **[Planned]**
- **Output is not executed:** answers are rendered as text; no tool-calling or
  code execution is driven by document content in MVP scope.
- **Citation verification:** cited spans are checked to exist in the source,
  reducing fabricated-citation risk. **[Planned]**
- **MVP groundwork:** the deterministic mock never executes or echoes retrieved
  instructions, and every streamed event is schema-validated on both ends,
  preventing malformed payloads from corrupting client state. **[MVP]**

## 5. Document privacy

- The project handles only **publicly shareable** documents. No real financial,
  personal, or confidential documents appear in fixtures, tests, or demos; all
  fixtures are explicitly fictional. **[MVP]**
- Uploaded documents, model weights, datasets, and generated artifacts are
  git-ignored and never committed. **[MVP]**
- Multi-tenant isolation and per-user access control are **out of scope** for
  the portfolio MVP and would require authentication + row-level authorization
  before any non-public use. **[Planned / non-goal for MVP]**

## 6. Transport, CORS, and headers

- CORS on the gateway is restricted to the configured web origin
  (`WEB_ORIGIN`), limited to the methods used. **[MVP]**
- TLS termination is expected at the deployment edge (reverse proxy / platform);
  local development uses plain HTTP on loopback. **[Planned for deploy]**
- Security headers, rate limiting, and request-size caps at the edge are
  planned for Day 14 hardening. **[Planned]**

## 7. Dependencies & supply chain

- Dependencies are kept minimal and version-pinned by range; lockfiles are
  committed. **[MVP]**
- CI runs lint, type checks, and tests on every change. Dependency and secret
  scanning can be layered onto CI during hardening. **[Planned]**

## 8. Denial of service

- The gateway applies upstream timeouts and propagates client disconnects to
  abort in-flight inference, bounding resource use per request. **[MVP]**
- Global rate limiting and concurrency caps are a Day 14 hardening item.
  **[Planned]**

## 9. Explicit non-goals (MVP)

Authentication/authorization, multi-tenancy, handling of sensitive or regulated
documents, and adversarial red-teaming of a real model. These are acknowledged
and deferred; none should be assumed present.

## 10. Reporting

This is a portfolio project, not a hosted service. Security issues can be raised
via a GitHub issue (once published) describing the concern and reproduction.
