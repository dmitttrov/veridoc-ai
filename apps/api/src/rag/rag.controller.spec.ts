import { BadRequestException } from '@nestjs/common';
import type { Request, Response } from 'express';
import { RagController } from './rag.controller';
import { AiClient } from '../ai/ai.client';

function fakeReq(): Request {
  return { on: jest.fn() } as unknown as Request;
}

function fakeRes(): Response & { chunks: string[]; ended: boolean } {
  const chunks: string[] = [];
  const res = {
    chunks,
    ended: false,
    status: jest.fn().mockReturnThis(),
    setHeader: jest.fn().mockReturnThis(),
    flushHeaders: jest.fn(),
    write: jest.fn((chunk: Uint8Array | string) => {
      chunks.push(typeof chunk === 'string' ? chunk : new TextDecoder().decode(chunk));
      return true;
    }),
    end: jest.fn(function () {
      res.ended = true;
    }),
    get writableEnded() {
      return res.ended;
    },
  };
  return res as unknown as Response & { chunks: string[]; ended: boolean };
}

function upstreamWith(records: string[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder();
      for (const r of records) controller.enqueue(encoder.encode(r));
      controller.close();
    },
  });
  return { ok: true, status: 200, body } as unknown as Response;
}

describe('RagController', () => {
  it('rejects an empty question', async () => {
    const ai = { openRagStream: jest.fn() } as unknown as AiClient;
    const controller = new RagController(ai);
    await expect(
      controller.rag({ question: '' }, fakeReq(), fakeRes()),
    ).rejects.toBeInstanceOf(BadRequestException);
    expect(ai.openRagStream).not.toHaveBeenCalled();
  });

  it('pipes the verified RAG stream through to the client', async () => {
    const records = [
      'data: {"type":"token","text":"Revenue "}\n\n',
      'data: {"type":"citations","citations":[{"documentId":"d","documentTitle":"t","page":2,"snippet":"s"}]}\n\n',
      'data: {"type":"done","mock":true,"model":"m","tokenCount":1,"abstained":false,"invalidCitationCount":0}\n\n',
    ];
    const ai = {
      openRagStream: jest.fn().mockResolvedValue(upstreamWith(records)),
    } as unknown as AiClient;
    const controller = new RagController(ai);
    const res = fakeRes();

    await controller.rag({ question: 'What was revenue?' }, fakeReq(), res);

    expect(ai.openRagStream).toHaveBeenCalledTimes(1);
    expect(res.chunks.join('')).toBe(records.join(''));
    expect(res.ended).toBe(true);
  });

  it('emits a terminal error event when the upstream fails', async () => {
    const ai = {
      openRagStream: jest.fn().mockRejectedValue(new Error('upstream down')),
    } as unknown as AiClient;
    const controller = new RagController(ai);
    const res = fakeRes();

    await controller.rag({ question: 'q' }, fakeReq(), res);
    const written = res.chunks.join('');
    expect(written).toContain('"type":"error"');
    expect(written).toContain('gateway_upstream_error');
  });
});
