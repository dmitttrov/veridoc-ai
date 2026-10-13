import type {
  ChatRequest,
  ChatStreamEvent,
  DocumentIngestionResult,
  DocumentSummary,
  RetrievalRequest,
  RetrievalResponse,
  StoredDocument,
} from '@veridoc/contracts';
import { parseSseStream } from './sse';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? 'http://localhost:3000';

export async function fetchDocuments(signal?: AbortSignal): Promise<DocumentSummary[]> {
  const resp = await fetch(`${API_BASE_URL}/api/documents`, { signal });
  if (!resp.ok) {
    throw new Error(`Failed to load documents (${resp.status})`);
  }
  return (await resp.json()) as DocumentSummary[];
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
  return (await resp.json()) as DocumentIngestionResult;
}

export async function fetchStoredDocuments(
  signal?: AbortSignal,
): Promise<StoredDocument[]> {
  const resp = await fetch(`${API_BASE_URL}/api/documents/stored`, { signal });
  if (!resp.ok) {
    throw await readError(resp, `Failed to load stored documents (${resp.status})`);
  }
  return (await resp.json()) as StoredDocument[];
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
  return (await resp.json()) as RetrievalResponse;
}
