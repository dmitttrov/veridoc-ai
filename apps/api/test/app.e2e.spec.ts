import type { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { AiClient, AiUpstreamError } from '../src/ai/ai.client';
import { AppModule } from '../src/app.module';

/**
 * End-to-end tests that boot the real Nest application (global exception
 * filter + throttler guard active) and drive it over HTTP with supertest.
 * The AI service is replaced with a mock so no network is touched.
 */
describe('API (e2e)', () => {
  let app: INestApplication;
  const ai = {
    retrieve: jest.fn(),
  };

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] })
      .overrideProvider(AiClient)
      .useValue(ai)
      .compile();
    app = moduleRef.createNestApplication();
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  it('GET /health returns the liveness envelope', async () => {
    const res = await request(app.getHttpServer()).get('/health').expect(200);
    expect(res.body).toMatchObject({ status: 'ok', service: 'veridoc-api' });
  });

  it('rejects an invalid body with the standard { code, message, issues } envelope', async () => {
    const res = await request(app.getHttpServer())
      .post('/api/retrieve')
      .send({ query: '' })
      .expect(400);
    expect(res.body).toMatchObject({ code: 'invalid_request' });
    expect(Array.isArray(res.body.issues)).toBe(true);
    expect(ai.retrieve).not.toHaveBeenCalled();
  });

  it('maps an upstream error to its status + code through the global filter', async () => {
    ai.retrieve.mockRejectedValueOnce(
      new AiUpstreamError(503, 'database_unavailable', 'down'),
    );
    const res = await request(app.getHttpServer())
      .post('/api/retrieve')
      .send({ query: 'revenue' })
      .expect(503);
    expect(res.body).toMatchObject({ code: 'database_unavailable' });
  });

  it('does not leak internals for an unexpected error (opaque 500)', async () => {
    ai.retrieve.mockRejectedValueOnce(new Error('secret stack detail'));
    const res = await request(app.getHttpServer())
      .post('/api/retrieve')
      .send({ query: 'revenue' })
      .expect(503);
    // A non-AiUpstreamError is surfaced as a generic gateway error, not the raw message.
    expect(res.body.code).toBe('gateway_upstream_error');
    expect(JSON.stringify(res.body)).not.toContain('secret stack detail');
  });
});

describe('rate limiting (e2e)', () => {
  let app: INestApplication;
  const saved = { max: process.env.RATE_LIMIT_MAX, ttl: process.env.RATE_LIMIT_TTL_MS };

  beforeAll(async () => {
    // Tight limit so a short burst trips the guard deterministically.
    process.env.RATE_LIMIT_MAX = '2';
    process.env.RATE_LIMIT_TTL_MS = '60000';
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] })
      .overrideProvider(AiClient)
      .useValue({ retrieve: jest.fn() })
      .compile();
    app = moduleRef.createNestApplication();
    await app.init();
  });

  afterAll(async () => {
    await app.close();
    process.env.RATE_LIMIT_MAX = saved.max;
    process.env.RATE_LIMIT_TTL_MS = saved.ttl;
  });

  it('returns 429 once the per-window limit is exceeded', async () => {
    const server = app.getHttpServer();
    await request(server).get('/health').expect(200);
    await request(server).get('/health').expect(200);
    await request(server).get('/health').expect(429);
  });
});
