import {
  BadRequestException,
  Controller,
  Get,
  HttpException,
  Logger,
  Post,
  UploadedFile,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import {
  UPLOAD_LIMITS,
  type DocumentIngestionResult,
  type StoredDocument,
} from '@veridoc/contracts';
import { AiClient, AiUpstreamError } from '../ai/ai.client';

/**
 * Multipart upload + stored-document listing.
 *
 * Size and content-type are validated at this public edge before anything is
 * forwarded to the internal AI service (which validates again — defense in
 * depth). Consistent with docs/SECURITY.md.
 */
@Controller('api/documents')
export class UploadController {
  private readonly logger = new Logger(UploadController.name);

  constructor(private readonly ai: AiClient) {}

  @Post('upload')
  @UseInterceptors(
    FileInterceptor('file', {
      limits: { fileSize: UPLOAD_LIMITS.maxBytes, files: 1 },
    }),
  )
  async upload(
    @UploadedFile() file?: Express.Multer.File,
  ): Promise<DocumentIngestionResult> {
    if (!file) {
      throw new BadRequestException({
        code: 'missing_file',
        message: 'A single `file` field containing a PDF is required.',
      });
    }
    const mime = ((file.mimetype || '').split(';')[0] ?? '').trim();
    if (!UPLOAD_LIMITS.allowedMimeTypes.includes(mime as 'application/pdf')) {
      throw new HttpException(
        { code: 'unsupported_media_type', message: `Unsupported content type: ${mime}` },
        415,
      );
    }

    try {
      return await this.ai.ingestDocument(file.buffer, file.originalname, mime);
    } catch (err) {
      throw this.mapUpstream(err);
    }
  }

  @Get('stored')
  async stored(): Promise<StoredDocument[]> {
    try {
      return await this.ai.listStoredDocuments();
    } catch (err) {
      throw this.mapUpstream(err);
    }
  }

  private mapUpstream(err: unknown): HttpException {
    if (err instanceof AiUpstreamError) {
      // Preserve the AI service's status + code; message is already sanitized.
      return new HttpException({ code: err.code, message: err.message }, err.status);
    }
    this.logger.error(`ingestion failed: ${(err as Error).message}`);
    return new HttpException(
      { code: 'gateway_upstream_error', message: 'Document service is unavailable.' },
      503,
    );
  }
}
