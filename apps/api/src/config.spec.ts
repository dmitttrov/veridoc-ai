import { loadConfig } from './config';

describe('loadConfig', () => {
  it('applies safe defaults when env is empty', () => {
    const config = loadConfig({});
    expect(config.PORT).toBe(3000);
    expect(config.AI_SERVICE_URL).toBe('http://127.0.0.1:8000');
    expect(config.AI_REQUEST_TIMEOUT_MS).toBe(30000);
  });

  it('coerces and validates provided values', () => {
    const config = loadConfig({ PORT: '4100', AI_SERVICE_URL: 'http://ai:9000' });
    expect(config.PORT).toBe(4100);
    expect(config.AI_SERVICE_URL).toBe('http://ai:9000');
  });

  it('throws on an invalid URL', () => {
    expect(() => loadConfig({ AI_SERVICE_URL: 'not-a-url' })).toThrow(
      /Invalid environment configuration/,
    );
  });
});
