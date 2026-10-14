import {
  BadRequestException,
  Body,
  Controller,
  Logger,
  Post,
  Req,
  Res,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import {
  RagRequestSchema,
  encodeSseEvent,
  type ChatStreamEvent,
} from '@veridoc/contracts';
import { AiClient } from '../ai/ai.client';

/**
 * Grounded RAG endpoint. Streams a VERIFIED answer (the AI service buffers the
 * model output and validates its citations before emitting anything), so the
 * browser never receives unverified claims presented as a final answer.
 */
@Controller('api/rag')
export class RagController {
  private readonly logger = new Logger(RagController.name);

  constructor(private readonly ai: AiClient) {}

  @Post()
  async rag(
    @Body() rawBody: unknown,
    @Req() req: Request,
    @Res() res: Response,
  ): Promise<void> {
    const parsed = RagRequestSchema.safeParse(rawBody);
    if (!parsed.success) {
      throw new BadRequestException({
        code: 'invalid_request',
        message: 'Invalid RAG request',
        issues: parsed.error.issues,
      });
    }

    const abort = new AbortController();
    req.on('close', () => abort.abort());

    res.status(200);
    res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
    res.setHeader('Cache-Control', 'no-cache, no-transform');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');
    res.flushHeaders?.();

    try {
      const upstream = await this.ai.openRagStream(parsed.data, abort.signal);
      const reader = upstream.body!.getReader();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        if (value) res.write(value);
      }
      res.end();
    } catch (err) {
      this.logger.error(`RAG stream failed: ${(err as Error).message}`);
      if (!res.writableEnded) {
        const event: ChatStreamEvent = {
          type: 'error',
          message: 'The assistant is temporarily unavailable. Please try again.',
          code: 'gateway_upstream_error',
        };
        res.write(encodeSseEvent(event));
        res.end();
      }
    }
  }
}
