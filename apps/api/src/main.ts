import 'reflect-metadata';
import { Logger } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { type NestExpressApplication } from '@nestjs/platform-express';
import { json } from 'express';
import helmet from 'helmet';
import { AppModule } from './app.module';
import { JsonLogger } from './common/json.logger';
import { loadConfig } from './config';

async function bootstrap(): Promise<void> {
  const config = loadConfig();
  const app = await NestFactory.create<NestExpressApplication>(AppModule, {
    bufferLogs: false,
  });

  // Structured JSON logs (with request-id correlation) in production; keep the
  // readable console logger in development.
  if (config.NODE_ENV === 'production') {
    app.useLogger(new JsonLogger());
  }

  // Security headers at the edge (CSP, HSTS, no-sniff, frame options, …).
  app.use(helmet());

  // Explicit JSON body limit. The contract permits message + up to 50 history
  // turns (~hundreds of KB), which exceeds Express's 100kb default; set a clear
  // ceiling so the HTTP limit and the zod limits agree (and to bound payloads).
  app.use(json({ limit: '1mb' }));

  // Restrict CORS to the known web origin. The AI service is never exposed here.
  app.enableCors({
    origin: config.WEB_ORIGIN,
    methods: ['GET', 'POST'],
  });

  // Behind an ingress/load balancer in production, trust the first proxy hop so
  // per-IP rate limiting and request logs see the real client IP (via
  // X-Forwarded-For) rather than the proxy's address. Left off in development,
  // where trusting a spoofable header would weaken the rate limiter.
  if (config.NODE_ENV === 'production') {
    app.set('trust proxy', 1);
  }

  // Request validation is handled explicitly with zod contracts in the
  // controllers (see ChatController), so no class-validator pipe is needed.
  app.enableShutdownHooks();

  await app.listen(config.PORT);
  new Logger('Bootstrap').log(
    `Veridoc API gateway listening on :${config.PORT} (AI service: ${config.AI_SERVICE_URL})`,
  );
}

void bootstrap();
