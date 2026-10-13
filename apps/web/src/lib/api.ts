import type {
  ChatRequest,
  ChatStreamEvent,
  DocumentSummary,
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
