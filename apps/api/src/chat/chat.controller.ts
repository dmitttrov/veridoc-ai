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
  ChatRequestSchema,
  encodeSseEvent,
  type ChatStreamEvent,
} from '@veridoc/contracts';
import { AiClient } from '../ai/ai.client';

/** Accepts chat requests from the browser and streams grounded answers (SSE). */
@Controller('api/chat')
export class ChatController {
  private readonly logger = new Logger(ChatController.name);

  constructor(private readonly ai: AiClient) {}

  @Post()
  async chat(
    @Body() rawBody: unknown,
    @Req() req: Request,
    @Res() res: Response,
  ): Promise<void> {
    const parsed = ChatRequestSchema.safeParse(rawBody);
    if (!parsed.success) {
      throw new BadRequestException({
        message: 'Invalid chat request',
        issues: parsed.error.issues,
      });
    }

    // Propagate client disconnects to the upstream request.
    const abort = new AbortController();
    req.on('close', () => abort.abort());

    res.status(200);
    res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
    res.setHeader('Cache-Control', 'no-cache, no-transform');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');
    res.flushHeaders?.();

    try {
      const upstream = await this.ai.openChatStream(parsed.data, abort.signal);
      const reader = upstream.body!.getReader();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        if (value) res.write(value);
      }
      res.end();
    } catch (err) {
      const message = (err as Error).message ?? 'Unknown error';
      this.logger.error(`Chat stream failed: ${message}`);
      // The stream may be mid-flight; emit a terminal error event instead of
      // an HTTP error so the client's SSE parser can surface it cleanly.
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
