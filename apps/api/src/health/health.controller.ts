import { Controller, Get } from '@nestjs/common';
import type { HealthStatus } from '@veridoc/contracts';

/** Liveness endpoint for the gateway itself (does not probe the AI service). */
@Controller('health')
export class HealthController {
  @Get()
  health(): HealthStatus {
    return {
      status: 'ok',
      service: 'veridoc-api',
      version: '0.1.0',
    };
  }
}
