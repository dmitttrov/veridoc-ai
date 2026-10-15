/**
 * @veridoc/contracts
 *
 * Single source of truth for the API contracts shared across the web client,
 * the NestJS gateway, and (by mirroring in Pydantic) the FastAPI AI service.
 *
 * Everything here is runtime-validated with zod so the gateway can reject
 * malformed input at the boundary, and the inferred TypeScript types are
 * re-exported for compile-time safety in the web and api workspaces.
 */
import { z } from 'zod';

/** Bumped whenever a breaking change is made to the contracts below. */
export const CONTRACTS_VERSION = '0.1.0' as const;

/* -------------------------------------------------------------------------- */
/* Documents                                                                  */
/* -------------------------------------------------------------------------- */

/**
 * A document available for question answering. In Phase 1 these come from a
 * static, synthetic fixture set (no real financial documents). Later phases
 * replace the source with ingested, user-uploaded documents in PostgreSQL.
 */
export const DocumentSummarySchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  /** Fictional issuer/company name — fixtures only. */
  issuer: z.string().min(1),
  /** Reporting period label, e.g. "FY2023" or "Q2 2024". */
  period: z.string().min(1),
  pageCount: z.number().int().positive(),
});
export type DocumentSummary = z.infer<typeof DocumentSummarySchema>;

/* -------------------------------------------------------------------------- */
/* Chat request                                                               */
/* -------------------------------------------------------------------------- */

export const ChatMessageRole = z.enum(['user', 'assistant']);
export type ChatMessageRole = z.infer<typeof ChatMessageRole>;

export const ChatMessageSchema = z.object({
  role: ChatMessageRole,
  content: z.string().min(1).max(8000),
});
export type ChatMessage = z.infer<typeof ChatMessageSchema>;

export const ChatRequestSchema = z.object({
  /** The new user question. */
  message: z.string().min(1, 'message must not be empty').max(8000),
  /** Optional prior turns for multi-turn context. */
  history: z.array(ChatMessageSchema).max(50).optional().default([]),
  /** Optional subset of document ids to ground the answer on. */
  documentIds: z.array(z.string().min(1)).max(50).optional().default([]),
});
export type ChatRequest = z.infer<typeof ChatRequestSchema>;

/* -------------------------------------------------------------------------- */
/* Citations                                                                  */
/* -------------------------------------------------------------------------- */

/**
 * A grounded source reference. In mock mode these point at fixture documents
 * so the end-to-end citation plumbing can be built and tested before real
 * retrieval exists.
 */
export const CitationSchema = z.object({
  documentId: z.string().min(1),
  documentTitle: z.string().min(1),
  page: z.number().int().positive(),
  /** Short quoted snippet that supports the answer. */
  snippet: z.string().min(1),
  /**
   * Phase 3 (grounded RAG): the retrieved chunk this citation was validated
   * against, and its character span in the stored, normalized page text. When
   * present, the citation is traceable to exact stored evidence.
   */
  chunkId: z.string().uuid().optional(),
  charStart: z.number().int().nonnegative().optional(),
  charEnd: z.number().int().nonnegative().optional(),
  /** The short evidence marker the model used, e.g. "E1". */
  marker: z.string().min(1).optional(),
});
export type Citation = z.infer<typeof CitationSchema>;

/* -------------------------------------------------------------------------- */
/* Streaming events (SSE payloads)                                            */
/* -------------------------------------------------------------------------- */

/**
 * The AI service and the gateway both emit Server-Sent Events whose `data:`
 * field is a JSON-encoded `ChatStreamEvent`. A stream is a sequence of
 * `token` events, optionally a `citations` event, then exactly one terminal
 * event (`done` or `error`).
 */
export const ChatStreamEventSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('token'),
    /** Incremental text delta to append to the answer. */
    text: z.string(),
  }),
  z.object({
    type: z.literal('citations'),
    citations: z.array(CitationSchema),
  }),
  z.object({
    type: z.literal('done'),
    /** Whether the answer was produced by the deterministic mock provider. */
    mock: z.boolean(),
    /** Provider/model identifier for observability. */
    model: z.string().min(1),
    /** Approximate number of generated tokens (coarse, for UX only). */
    tokenCount: z.number().int().nonnegative(),
    /**
     * Phase 3 (grounded RAG): true when the system declined to answer because
     * the retrieved evidence was insufficient.
     */
    abstained: z.boolean().optional(),
    /**
     * Phase 3: number of citation markers the model emitted that did not map to
     * any retrieved evidence (fabricated references, which were rejected).
     */
    invalidCitationCount: z.number().int().nonnegative().optional(),
  }),
  z.object({
    type: z.literal('error'),
    message: z.string().min(1),
    /** Stable, machine-readable error code. */
    code: z.string().min(1),
  }),
]);
export type ChatStreamEvent = z.infer<typeof ChatStreamEventSchema>;

export type TokenEvent = Extract<ChatStreamEvent, { type: 'token' }>;
export type CitationsEvent = Extract<ChatStreamEvent, { type: 'citations' }>;
export type DoneEvent = Extract<ChatStreamEvent, { type: 'done' }>;
export type ErrorEvent = Extract<ChatStreamEvent, { type: 'error' }>;

/** Encode an event as a single SSE record terminated by a blank line. */
export function encodeSseEvent(event: ChatStreamEvent): string {
  return `data: ${JSON.stringify(event)}\n\n`;
}

/* -------------------------------------------------------------------------- */
/* Health                                                                     */
/* -------------------------------------------------------------------------- */

export const HealthStatusSchema = z.object({
  status: z.enum(['ok', 'degraded']),
  service: z.string().min(1),
  version: z.string().min(1),
  /** True when the service is serving deterministic mock inference. */
  mock: z.boolean().optional(),
});
export type HealthStatus = z.infer<typeof HealthStatusSchema>;

/* -------------------------------------------------------------------------- */
/* Document ingestion (Phase 2)                                               */
/* -------------------------------------------------------------------------- */

/** Lifecycle state of an ingestion run. Mirrors the DB `ingestion_state` enum. */
export const IngestionStateSchema = z.enum([
  'pending',
  'running',
  'succeeded',
  'failed',
]);
export type IngestionState = z.infer<typeof IngestionStateSchema>;

/**
 * The outcome of ingesting a single uploaded PDF. `alreadyIngested` is true when
 * an identical file (same SHA-256 content hash) was already stored — ingestion
 * is idempotent, so no duplicate records are created.
 */
export const DocumentIngestionResultSchema = z.object({
  documentId: z.string().uuid(),
  filename: z.string().min(1),
  contentHash: z.string().length(64),
  mimeType: z.string().min(1),
  sizeBytes: z.number().int().nonnegative(),
  pageCount: z.number().int().nonnegative(),
  chunkCount: z.number().int().nonnegative(),
  state: IngestionStateSchema,
  alreadyIngested: z.boolean(),
  /** Present only when `state` is `failed`. */
  error: z.string().nullable().optional(),
});
export type DocumentIngestionResult = z.infer<typeof DocumentIngestionResultSchema>;

/** A document that has been ingested and stored (available for retrieval). */
export const StoredDocumentSchema = z.object({
  id: z.string().uuid(),
  title: z.string().min(1),
  filename: z.string().min(1),
  pageCount: z.number().int().nonnegative(),
  chunkCount: z.number().int().nonnegative(),
  sizeBytes: z.number().int().nonnegative(),
});
export type StoredDocument = z.infer<typeof StoredDocumentSchema>;

/** Upload constraints shared by the gateway and the AI service. */
export const UPLOAD_LIMITS = {
  /** Maximum accepted upload size in bytes (25 MiB). */
  maxBytes: 25 * 1024 * 1024,
  /** Maximum accepted page count. */
  maxPages: 300,
  /** The only accepted MIME type in Phase 2. */
  allowedMimeTypes: ['application/pdf'] as const,
} as const;

/* -------------------------------------------------------------------------- */
/* Retrieval (Phase 2)                                                        */
/* -------------------------------------------------------------------------- */

export const RetrievalRequestSchema = z.object({
  query: z.string().min(1, 'query must not be empty').max(2000),
  /** Optional subset of document ids to restrict retrieval to. */
  documentIds: z.array(z.string().uuid()).max(50).optional().default([]),
  /** Number of passages to return. */
  topK: z.number().int().positive().max(50).optional().default(5),
  /**
   * Override the server's default reranking behaviour. When omitted, the
   * server applies reranking iff a reranker is configured and available.
   */
  rerank: z.boolean().optional(),
});
export type RetrievalRequest = z.infer<typeof RetrievalRequestSchema>;

/** Per-strategy and fused retrieval scores for a passage. */
export const RetrievalScoresSchema = z.object({
  /** PostgreSQL full-text rank (ts_rank_cd); 0 when not matched lexically. */
  lexical: z.number(),
  /** Cosine similarity in [0, 1]; 0 when not matched semantically. */
  semantic: z.number(),
  /** Reciprocal-rank-fusion score used for candidate ordering. */
  fused: z.number(),
  /**
   * Cross-encoder reranker score. Present only when reranking was applied.
   * This is a DIFFERENT quantity from `fused` and the two must not be
   * compared or combined — they live on different scales.
   */
  rerank: z.number().nullable().optional(),
});
export type RetrievalScores = z.infer<typeof RetrievalScoresSchema>;

/**
 * A retrieved source passage. This is EVIDENCE, not an AI-generated answer.
 * Every field traces back to stored, normalized page text: `text` is exactly
 * `document_pages.normalized_text[charStart:charEnd]` for the given page.
 */
export const RetrievedPassageSchema = z.object({
  chunkId: z.string().uuid(),
  documentId: z.string().uuid(),
  documentTitle: z.string().min(1),
  page: z.number().int().positive(),
  /** Exact retrieved text, verbatim from stored page text. */
  text: z.string(),
  charStart: z.number().int().nonnegative(),
  charEnd: z.number().int().nonnegative(),
  scores: RetrievalScoresSchema,
  /** Stable, human-readable citation reference, e.g. "Acme FY2023, p.12". */
  citation: z.string().min(1),
});
export type RetrievedPassage = z.infer<typeof RetrievedPassageSchema>;

/* -------------------------------------------------------------------------- */
/* Grounded RAG (Phase 3)                                                     */
/* -------------------------------------------------------------------------- */

export const RagRequestSchema = z.object({
  question: z.string().min(1, 'question must not be empty').max(2000),
  /** Optional subset of document ids to restrict grounding to. */
  documentIds: z.array(z.string().uuid()).max(50).optional().default([]),
  /** Number of evidence passages to ground on. */
  topK: z.number().int().positive().max(20).optional().default(5),
  /** Override server default reranking behaviour. */
  rerank: z.boolean().optional(),
});
export type RagRequest = z.infer<typeof RagRequestSchema>;

export const RetrievalResponseSchema = z.object({
  query: z.string(),
  passages: z.array(RetrievedPassageSchema),
  /** Identity of the embedding model used for the semantic leg. */
  embeddingModel: z.string().min(1),
  /** Dimensionality of the embedding vectors. */
  embeddingDim: z.number().int().positive(),
  /** Whether cross-encoder reranking was applied to produce the final order. */
  reranked: z.boolean(),
  /** Identity of the reranker model, when reranking was applied. */
  rerankerModel: z.string().nullable(),
});
export type RetrievalResponse = z.infer<typeof RetrievalResponseSchema>;
