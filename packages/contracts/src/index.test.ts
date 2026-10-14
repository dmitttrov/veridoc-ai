import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { z } from 'zod';
import {
  ChatMessageSchema,
  ChatRequestSchema,
  ChatStreamEventSchema,
  CitationSchema,
  DocumentIngestionResultSchema,
  DocumentSummarySchema,
  HealthStatusSchema,
  RagRequestSchema,
  RetrievalRequestSchema,
  RetrievalResponseSchema,
  RetrievalScoresSchema,
  RetrievedPassageSchema,
  StoredDocumentSchema,
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

/**
 * Golden wire-shape contract. The same JSON fixtures are validated by the
 * Python suite (services/ai/tests/test_wire_contract.py). Because the zod and
 * Pydantic definitions are hand-mirrored, this shared fixture is what actually
 * prevents silent drift: a field renamed/added/removed/retyped on either side
 * fails the round-trip in CI.
 */
const fixtures = JSON.parse(
  readFileSync(fileURLToPath(new URL('../wire-fixtures.json', import.meta.url)), 'utf8'),
) as Record<string, unknown>;

const WIRE_CASES: Array<[string, z.ZodTypeAny]> = [
  ['documentSummary', DocumentSummarySchema],
  ['chatMessage', ChatMessageSchema],
  ['chatRequest', ChatRequestSchema],
  ['citation', CitationSchema],
  ['tokenEvent', ChatStreamEventSchema],
  ['citationsEvent', ChatStreamEventSchema],
  ['doneEvent', ChatStreamEventSchema],
  ['errorEvent', ChatStreamEventSchema],
  ['healthStatus', HealthStatusSchema],
  ['documentIngestionResult', DocumentIngestionResultSchema],
  ['storedDocument', StoredDocumentSchema],
  ['retrievalRequest', RetrievalRequestSchema],
  ['retrievalScores', RetrievalScoresSchema],
  ['retrievedPassage', RetrievedPassageSchema],
  ['ragRequest', RagRequestSchema],
  ['retrievalResponse', RetrievalResponseSchema],
];

describe('golden wire-shape fixtures (shared with the Python suite)', () => {
  it.each(WIRE_CASES)('round-trips %s against its zod schema', (key, schema) => {
    const instance = fixtures[key];
    expect(instance, `fixture "${key}" is missing`).toBeDefined();
    const parsed = schema.parse(instance);
    // Deep, order-independent equality: fails if the schema would strip a field
    // (removed on this side) or inject one via a default (optionality drift).
    expect(parsed).toEqual(instance);
  });
});
