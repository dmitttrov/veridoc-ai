import { ChatStreamEventSchema, type ChatStreamEvent } from '@veridoc/contracts';

/**
 * Parse a `ReadableStream` of SSE bytes into validated `ChatStreamEvent`s.
 *
 * Handles chunk boundaries that split an SSE record, and validates every
 * event against the shared contract so malformed payloads surface loudly
 * rather than corrupting UI state.
 */
export async function* parseSseStream(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    for (;;) {
      if (signal?.aborted) return;
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE records are separated by a blank line.
      let sep: number;
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const record = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const event = parseRecord(record);
        if (event) yield event;
      }
    }

    // Flush any trailing record without a terminating blank line.
    const tail = parseRecord(buffer);
    if (tail) yield tail;
  } finally {
    reader.releaseLock();
  }
}

function parseRecord(record: string): ChatStreamEvent | null {
  const dataLines = record
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice('data:'.length).trim());

  if (dataLines.length === 0) return null;
  const payload = dataLines.join('\n');
  if (payload === '' || payload === '[DONE]') return null;

  const parsed = ChatStreamEventSchema.safeParse(JSON.parse(payload));
  return parsed.success ? parsed.data : null;
}
