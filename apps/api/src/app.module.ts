import { Module } from '@nestjs/common';
import { AiClient } from './ai/ai.client';
import { ChatController } from './chat/chat.controller';
import { CONFIG, loadConfig } from './config';
import { DocumentsController } from './documents/documents.controller';
import { UploadController } from './documents/upload.controller';
import { HealthController } from './health/health.controller';
import { RetrieveController } from './retrieve/retrieve.controller';

@Module({
  controllers: [
    HealthController,
    ChatController,
    DocumentsController,
    UploadController,
    RetrieveController,
  ],
  providers: [
    {
      provide: CONFIG,
      useFactory: () => loadConfig(),
    },
    AiClient,
  ],
})
export class AppModule {}
