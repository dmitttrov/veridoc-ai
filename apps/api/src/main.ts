import 'reflect-metadata';
import { Logger } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { loadConfig } from './config';

async function bootstrap(): Promise<void> {
  const config = loadConfig();
  const app = await NestFactory.create(AppModule, { bufferLogs: false });

  // Restrict CORS to the known web origin. The AI service is never exposed here.
  app.enableCors({
    origin: config.WEB_ORIGIN,
    methods: ['GET', 'POST'],
  });

  // Request validation is handled explicitly with zod contracts in the
  // controllers (see ChatController), so no class-validator pipe is needed.
  app.enableShutdownHooks();

  await app.listen(config.PORT);
  new Logger('Bootstrap').log(
    `Veridoc API gateway listening on :${config.PORT} (AI service: ${config.AI_SERVICE_URL})`,
  );
}

void bootstrap();
