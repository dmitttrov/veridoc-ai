import { Controller, Get, Res } from '@nestjs/common';
import { SkipThrottle } from '@nestjs/throttler';
import type { HealthStatus } from '@veridoc/contracts';
import type { Response } from 'express';
import { AiClient } from '../ai/ai.client';

/**
 * Health endpoints for the gateway. Excluded from rate limiting so that
 * load-balancer / orchestrator probes polling frequently are never throttled
 * (a 429'd probe would mark a healthy instance down).
 *
 * `/health` is liveness (the gateway process is up). `/ready` is readiness: it
 * probes the internal AI service and reports `degraded` (HTTP 503) when the only
 * upstream cannot serve, so traffic is not routed to a gateway whose dependency
 * is down.
 */
@SkipThrottle()
@Controller()
export class HealthController {
  constructor(private readonly ai: AiClient) {}

  @Get('health')
  health(): HealthStatus {
    return {
      status: 'ok',
      service: 'veridoc-api',
      version: '0.1.0',
    };
  }

  @Get('ready')
  async ready(@Res({ passthrough: true }) res: Response): Promise<HealthStatus> {
    const { ready } = await this.ai.checkReady();
    if (!ready) {
      res.status(503);
    }
    return {
      status: ready ? 'ok' : 'degraded',
      service: 'veridoc-api',
      version: '0.1.0',
    };
  }
}
