import { describe, expect, it } from 'vitest';
import type { ChatStreamEvent } from '@veridoc/contracts';
import { parseSseStream } from './sse';

function streamFrom(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<ChatStreamEvent[]> {
  const out: ChatStreamEvent[] = [];
  for await (const event of parseSseStream(stream)) out.push(event);
  return out;
}

describe('parseSseStream', () => {
  it('parses complete records', async () => {
    const events = await collect(
      streamFrom([
        'data: {"type":"token","text":"Hello "}\n\n',
        'data: {"type":"token","text":"world"}\n\n',
        'data: {"type":"done","mock":true,"model":"m","tokenCount":2}\n\n',
      ]),
    );
    expect(events.map((e) => e.type)).toEqual(['token', 'token', 'done']);
  });

  it('reassembles records split across chunk boundaries', async () => {
    const events = await collect(
      streamFrom(['data: {"type":"to', 'ken","text":"hi"}\n\n']),
    );
    expect(events).toEqual([{ type: 'token', text: 'hi' }]);
  });

  it('ignores malformed payloads rather than throwing', async () => {
    const events = await collect(
      streamFrom([
        'data: {"type":"token","text":"ok"}\n\n',
        'data: {"type":"unknown"}\n\n',
      ]),
    );
    expect(events).toEqual([{ type: 'token', text: 'ok' }]);
  });

  it('flushes a trailing record without a blank line', async () => {
    const events = await collect(streamFrom(['data: {"type":"token","text":"tail"}']));
    expect(events).toEqual([{ type: 'token', text: 'tail' }]);
  });
});
