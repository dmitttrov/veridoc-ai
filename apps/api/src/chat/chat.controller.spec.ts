import { BadRequestException } from '@nestjs/common';
import type { Request, Response } from 'express';
import { ChatController } from './chat.controller';
import { AiClient } from '../ai/ai.client';

/** Minimal Express Request stub (only what the controller touches). */
function fakeReq(): Request {
  return { on: jest.fn() } as unknown as Request;
}

/** Express Response stub that records written chunks. */
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
    end: jest.fn(function (this: { ended: boolean }) {
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

describe('ChatController', () => {
  it('rejects an invalid request body before streaming', async () => {
    const ai = { openChatStream: jest.fn() } as unknown as AiClient;
    const controller = new ChatController(ai);

    await expect(
      controller.chat({ message: '' }, fakeReq(), fakeRes()),
    ).rejects.toBeInstanceOf(BadRequestException);
    expect(ai.openChatStream).not.toHaveBeenCalled();
  });

  it('pipes upstream SSE records to the response', async () => {
    const records = [
      'data: {"type":"token","text":"Hello "}\n\n',
      'data: {"type":"done","mock":true,"model":"m","tokenCount":1}\n\n',
    ];
    const ai = {
      openChatStream: jest.fn().mockResolvedValue(upstreamWith(records)),
    } as unknown as AiClient;
    const controller = new ChatController(ai);
    const res = fakeRes();

    await controller.chat({ message: 'Hi' }, fakeReq(), res);

    expect(ai.openChatStream).toHaveBeenCalledTimes(1);
    expect(res.chunks.join('')).toBe(records.join(''));
    expect(res.ended).toBe(true);
  });

  it('emits a terminal error event when the upstream fails', async () => {
    const ai = {
      openChatStream: jest.fn().mockRejectedValue(new Error('upstream down')),
    } as unknown as AiClient;
    const controller = new ChatController(ai);
    const res = fakeRes();

    await controller.chat({ message: 'Hi' }, fakeReq(), res);

    const written = res.chunks.join('');
    expect(written).toContain('"type":"error"');
    expect(written).toContain('gateway_upstream_error');
    expect(res.ended).toBe(true);
  });
});
