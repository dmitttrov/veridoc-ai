import { getRequestId, requestContext, sanitizeRequestId } from './request-context';

describe('sanitizeRequestId', () => {
  it('accepts a short, safe token', () => {
    expect(sanitizeRequestId('abc-123_ID.4')).toBe('abc-123_ID.4');
  });

  it('rejects unsafe, empty, or over-long values (log-forging / injection)', () => {
    expect(sanitizeRequestId('bad id with spaces')).toBeUndefined();
    expect(sanitizeRequestId('a\nb')).toBeUndefined();
    expect(sanitizeRequestId('')).toBeUndefined();
    expect(sanitizeRequestId('x'.repeat(129))).toBeUndefined();
    expect(sanitizeRequestId(undefined)).toBeUndefined();
  });

  it('takes the first value when a header is provided as an array', () => {
    expect(sanitizeRequestId(['first', 'second'])).toBe('first');
  });
});

describe('requestContext', () => {
  it('exposes the id inside a run() scope and nothing outside it', () => {
    expect(getRequestId()).toBeUndefined();
    requestContext.run({ requestId: 'req-1' }, () => {
      expect(getRequestId()).toBe('req-1');
    });
    expect(getRequestId()).toBeUndefined();
  });
});
