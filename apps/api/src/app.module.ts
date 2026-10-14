import { Module } from '@nestjs/common';
import { APP_FILTER, APP_GUARD } from '@nestjs/core';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import { AiClient } from './ai/ai.client';
import { ChatController } from './chat/chat.controller';
import { AllExceptionsFilter } from './common/all-exceptions.filter';
import { CONFIG, loadConfig } from './config';
import { DocumentsController } from './documents/documents.controller';
import { UploadController } from './documents/upload.controller';
import { HealthController } from './health/health.controller';
import { RagController } from './rag/rag.controller';
import { RetrieveController } from './retrieve/retrieve.controller';

@Module({
  imports: [
    // Per-IP rate limiting at the public edge; window + max come from config.
    // The factory reads config lazily (at module init) so tests can set env first.
    ThrottlerModule.forRootAsync({
      useFactory: () => {
        const config = loadConfig();
        return {
          throttlers: [{ ttl: config.RATE_LIMIT_TTL_MS, limit: config.RATE_LIMIT_MAX }],
        };
      },
    }),
  ],
  controllers: [
    HealthController,
    ChatController,
    DocumentsController,
    UploadController,
    RetrieveController,
    RagController,
  ],
  providers: [
    {
      provide: CONFIG,
      useFactory: () => loadConfig(),
    },
    AiClient,
    // Global rate-limit guard and a single error-shaping filter.
    { provide: APP_GUARD, useClass: ThrottlerGuard },
    { provide: APP_FILTER, useClass: AllExceptionsFilter },
  ],
})
export class AppModule {}
