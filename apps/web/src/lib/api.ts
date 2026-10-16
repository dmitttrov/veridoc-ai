import {
  type ChatRequest,
  type ChatStreamEvent,
  type DocumentIngestionResult,
  DocumentIngestionResultSchema,
  type DocumentSummary,
  DocumentSummarySchema,
  type RagRequest,
  type RetrievalRequest,
  type RetrievalResponse,
  RetrievalResponseSchema,
  type StoredDocument,
  StoredDocumentSchema,
} from '@veridoc/contracts';
import { z } from 'zod';
import { parseSseStream } from './sse';

/**
 * Resolve the gateway base URL, in priority order:
 *   1. Runtime config the container injects at startup (window.__VERIDOC_ENV__,
 *      served as /env.js) — lets one built image serve any environment.
 *   2. Build-time VITE_API_BASE_URL (the Vite dev server).
 *   3. A local-dev default.
 * An explicit empty string means "same origin" — requests go to /api/... behind
 * an ingress that routes /api to the gateway — so unset must be distinguished
 * from "" (hence the `!== undefined` check rather than `??`).
 */
function resolveApiBaseUrl(): string {
  const runtime = (globalThis as { __VERIDOC_ENV__?: { API_BASE_URL?: string } })
    .__VERIDOC_ENV__?.API_BASE_URL;
  const base =
    runtime !== undefined
      ? runtime
      : (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:3000');
  return base.replace(/\/$/, '');
}

const API_BASE_URL = resolveApiBaseUrl();

/**
 * Parse a JSON response against the shared contract. Responses are untrusted
 * over the wire, so we validate at the boundary (like the SSE stream does)
 * rather than casting — a shape mismatch fails loudly here instead of surfacing
 * as a confusing render error deep in the tree.
 */
async function parseJson<T>(resp: Response, schema: z.ZodType<T>): Promise<T> {
  const data: unknown = await resp.json();
  const result = schema.safeParse(data);
  if (!result.success) {
    throw new Error('Unexpected response shape from the server');
  }
  return result.data;
}

export async function fetchDocuments(signal?: AbortSignal): Promise<DocumentSummary[]> {
  const resp = await fetch(`${API_BASE_URL}/api/documents`, { signal });
  if (!resp.ok) {
    throw new Error(`Failed to load documents (${resp.status})`);
  }
  return parseJson(resp, z.array(DocumentSummarySchema));
}

/**
 * Submit a chat request and yield streamed events as they arrive.
 * Throws only on failure to *open* the stream; mid-stream failures are
 * delivered as `error` events by the gateway.
 */
export async function* streamChat(
  request: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const resp = await fetch(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(request),
    signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`Chat request failed (${resp.status})`);
  }

  yield* parseSseStream(resp.body, signal);
}

/**
 * Submit a grounded-RAG question. The gateway streams a VERIFIED answer (the AI
 * service validates citations before emitting), delivered as the same typed SSE
 * event union as chat (`token` | `citations` | `done` | `error`).
 */
export async function* streamRag(
  request: RagRequest,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const resp = await fetch(`${API_BASE_URL}/api/rag`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(request),
    signal,
  });
  if (!resp.ok || !resp.body) {
    throw new Error(`RAG request failed (${resp.status})`);
  }
  yield* parseSseStream(resp.body, signal);
}

/** Decode a gateway error body of shape `{ code, message }` when present. */
async function readError(resp: Response, fallback: string): Promise<Error> {
  try {
    const body = (await resp.json()) as { message?: string };
    return new Error(body?.message || fallback);
  } catch {
    return new Error(fallback);
  }
}

export async function uploadDocument(
  file: File,
  signal?: AbortSignal,
): Promise<DocumentIngestionResult> {
  const form = new FormData();
  form.append('file', file, file.name);
  const resp = await fetch(`${API_BASE_URL}/api/documents/upload`, {
    method: 'POST',
    body: form,
    signal,
  });
  if (!resp.ok) {
    throw await readError(resp, `Upload failed (${resp.status})`);
  }
  return parseJson(resp, DocumentIngestionResultSchema);
}

export async function fetchStoredDocuments(
  signal?: AbortSignal,
): Promise<StoredDocument[]> {
  const resp = await fetch(`${API_BASE_URL}/api/documents/stored`, { signal });
  if (!resp.ok) {
    throw await readError(resp, `Failed to load stored documents (${resp.status})`);
  }
  return parseJson(resp, z.array(StoredDocumentSchema));
}

export async function retrieve(
  request: RetrievalRequest,
  signal?: AbortSignal,
): Promise<RetrievalResponse> {
  const resp = await fetch(`${API_BASE_URL}/api/retrieve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  });
  if (!resp.ok) {
    throw await readError(resp, `Retrieval failed (${resp.status})`);
  }
  return parseJson(resp, RetrievalResponseSchema);
}
