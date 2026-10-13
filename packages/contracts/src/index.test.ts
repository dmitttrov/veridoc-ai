import { describe, expect, it } from 'vitest';
import {
  ChatRequestSchema,
  ChatStreamEventSchema,
  RetrievalRequestSchema,
  encodeSseEvent,
  type ChatStreamEvent,
} from './index';

describe('ChatRequestSchema', () => {
  it('applies defaults for optional fields', () => {
    const parsed = ChatRequestSchema.parse({ message: 'What was revenue?' });
    expect(parsed.history).toEqual([]);
    expect(parsed.documentIds).toEqual([]);
  });

  it('rejects an empty message', () => {
    const result = ChatRequestSchema.safeParse({ message: '' });
    expect(result.success).toBe(false);
  });

  it('rejects an over-long message', () => {
    const result = ChatRequestSchema.safeParse({ message: 'x'.repeat(8001) });
    expect(result.success).toBe(false);
  });
});

describe('ChatStreamEventSchema', () => {
  it('discriminates by type', () => {
    const token: ChatStreamEvent = { type: 'token', text: 'hi' };
    expect(ChatStreamEventSchema.parse(token)).toEqual(token);
  });

  it('rejects an unknown event type', () => {
    const result = ChatStreamEventSchema.safeParse({ type: 'nope' });
    expect(result.success).toBe(false);
  });
});

describe('RetrievalRequestSchema', () => {
  it('defaults topK and documentIds', () => {
    const parsed = RetrievalRequestSchema.parse({ query: 'revenue' });
    expect(parsed.topK).toBe(5);
    expect(parsed.documentIds).toEqual([]);
  });

  it('rejects a non-uuid document id', () => {
    const result = RetrievalRequestSchema.safeParse({
      query: 'revenue',
      documentIds: ['not-a-uuid'],
    });
    expect(result.success).toBe(false);
  });
});

describe('encodeSseEvent', () => {
  it('produces a well-formed SSE record', () => {
    const record = encodeSseEvent({ type: 'token', text: 'hello' });
    expect(record).toBe('data: {"type":"token","text":"hello"}\n\n');
  });
});
