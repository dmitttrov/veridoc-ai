import { HealthController } from './health.controller';

describe('HealthController', () => {
  it('reports ok status for the gateway', () => {
    const controller = new HealthController();
    const result = controller.health();
    expect(result.status).toBe('ok');
    expect(result.service).toBe('veridoc-api');
  });
});
