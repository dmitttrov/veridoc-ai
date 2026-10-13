import { BadRequestException, Body, Controller, HttpException, Post } from '@nestjs/common';
import { RetrievalRequestSchema, type RetrievalResponse } from '@veridoc/contracts';
import { AiClient, AiUpstreamError } from '../ai/ai.client';

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
      if (err instanceof AiUpstreamError) {
        throw new HttpException({ code: err.code, message: err.message }, err.status);
      }
      throw new HttpException(
        { code: 'gateway_upstream_error', message: 'Retrieval service is unavailable.' },
        503,
      );
    }
  }
}
