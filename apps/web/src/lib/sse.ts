import { ChatStreamEventSchema, type ChatStreamEvent } from '@veridoc/contracts';

/**
 * Parse a `ReadableStream` of SSE bytes into validated `ChatStreamEvent`s.
 *
 * Handles chunk boundaries that split an SSE record, and validates every record
 * against the shared contract:
 *
 *  - A record that is **not valid JSON** is tolerated and skipped — transport
 *    noise / keepalive artifacts must not abort a live stream.
 *  - A record that **is valid JSON but fails the contract schema** is treated as
 *    contract drift and **surfaced loudly**: the parser yields a synthetic
 *    `error` event (`code: "contract_violation"`) and ends the stream. This is
 *    the opposite of silently dropping it — a renamed/removed field can no
 *    longer make a `done`/`citations` event vanish and hang or corrupt the UI.
 */
type ParseResult =
  | { kind: 'event'; event: ChatStreamEvent }
  | { kind: 'skip' }
  | { kind: 'drift'; reason: string };

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
        const result = parseRecord(record);
        if (result.kind === 'event') {
          yield result.event;
        } else if (result.kind === 'drift') {
          yield driftEvent(result.reason);
          return;
        }
      }
    }

    // Flush any trailing record without a terminating blank line.
    const tail = parseRecord(buffer);
    if (tail.kind === 'event') yield tail.event;
    else if (tail.kind === 'drift') yield driftEvent(tail.reason);
  } finally {
    reader.releaseLock();
  }
}

function driftEvent(reason: string): ChatStreamEvent {
  return {
    type: 'error',
    code: 'contract_violation',
    message: `Stream event failed contract validation: ${reason}`,
  };
}

function parseRecord(record: string): ParseResult {
  const dataLines = record
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice('data:'.length).trim());

  if (dataLines.length === 0) return { kind: 'skip' };
  const payload = dataLines.join('\n');
  if (payload === '' || payload === '[DONE]') return { kind: 'skip' };

  // Not valid JSON: tolerate transport noise; never abort a live stream.
  let json: unknown;
  try {
    json = JSON.parse(payload);
  } catch {
    return { kind: 'skip' };
  }

  // Valid JSON that fails the shared contract is drift — surface it loudly.
  const parsed = ChatStreamEventSchema.safeParse(json);
  if (!parsed.success) {
    return { kind: 'drift', reason: parsed.error.issues[0]?.message ?? 'unknown' };
  }
  return { kind: 'event', event: parsed.data };
}
