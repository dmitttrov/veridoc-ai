import { Controller, Get, Logger, ServiceUnavailableException } from '@nestjs/common';
import type { DocumentSummary } from '@veridoc/contracts';
import { AiClient } from '../ai/ai.client';

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
      this.logger.error(`Failed to list documents: ${(err as Error).message}`);
      throw new ServiceUnavailableException('Document service is unavailable');
    }
  }
}
