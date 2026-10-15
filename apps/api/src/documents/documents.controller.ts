import { Controller, Get, Logger } from '@nestjs/common';
import type { DocumentSummary } from '@veridoc/contracts';
import { AiClient } from '../ai/ai.client';
import { mapUpstreamError } from '../common/upstream-error';

/** Exposes the available documents to the web client. */
@Controller('api/documents')
export class DocumentsController {
  private readonly logger = new Logger(DocumentsController.name);

  constructor(private readonly ai: AiClient) {}

  @Get()
  async list(): Promise<DocumentSummary[]> {
    try {
      return await this.ai.listDocuments();
    } catch (err) {
      throw mapUpstreamError(err, this.logger);
    }
  }
}
