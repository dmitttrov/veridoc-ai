import type { Response } from 'express';
import type { AiClient } from '../ai/ai.client';
import { HealthController } from './health.controller';

function makeRes(): Response & { statusCode: number } {
  const res = {
    statusCode: 200,
    status(code: number) {
      this.statusCode = code;
      return this;
    },
  };
  return res as unknown as Response & { statusCode: number };
}

describe('HealthController', () => {
  it('reports ok status for the gateway liveness probe', () => {
    const controller = new HealthController({} as AiClient);
    const result = controller.health();
    expect(result.status).toBe('ok');
    expect(result.service).toBe('veridoc-api');
  });

  it('readiness is ok (200) when the AI service is ready', async () => {
    const ai = { checkReady: async () => ({ ready: true }) } as unknown as AiClient;
    const controller = new HealthController(ai);
    const res = makeRes();
    const result = await controller.ready(res);
    expect(result.status).toBe('ok');
    expect(res.statusCode).toBe(200);
  });

  it('readiness is degraded (503) when the AI service is not ready', async () => {
    const ai = { checkReady: async () => ({ ready: false }) } as unknown as AiClient;
    const controller = new HealthController(ai);
    const res = makeRes();
    const result = await controller.ready(res);
    expect(result.status).toBe('degraded');
    expect(res.statusCode).toBe(503);
  });
});
