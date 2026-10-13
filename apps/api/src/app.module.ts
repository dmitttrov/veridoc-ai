import { Module } from '@nestjs/common';
import { AiClient } from './ai/ai.client';
import { ChatController } from './chat/chat.controller';
import { CONFIG, loadConfig } from './config';
import { DocumentsController } from './documents/documents.controller';
import { HealthController } from './health/health.controller';

@Module({
  controllers: [HealthController, ChatController, DocumentsController],
  providers: [
    {
      provide: CONFIG,
      useFactory: () => loadConfig(),
    },
    AiClient,
  ],
})
export class AppModule {}
