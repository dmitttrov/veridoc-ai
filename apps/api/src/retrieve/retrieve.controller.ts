import { BadRequestException, Body, Controller, Post } from '@nestjs/common';
import { RetrievalRequestSchema, type RetrievalResponse } from '@veridoc/contracts';
import { AiClient } from '../ai/ai.client';
import { mapUpstreamError } from '../common/upstream-error';

/** Hybrid retrieval. Returns source passages (evidence), not generated answers. */
@Controller('api/retrieve')
export class RetrieveController {
  constructor(private readonly ai: AiClient) {}

  @Post()
  async retrieve(@Body() rawBody: unknown): Promise<RetrievalResponse> {
    const parsed = RetrievalRequestSchema.safeParse(rawBody);
    if (!parsed.success) {
      throw new BadRequestException({
        code: 'invalid_request',
        message: 'Invalid retrieval request',
        issues: parsed.error.issues,
      });
    }
    try {
      return await this.ai.retrieve(parsed.data);
    } catch (err) {
      throw mapUpstreamError(err);
    }
  }
}
