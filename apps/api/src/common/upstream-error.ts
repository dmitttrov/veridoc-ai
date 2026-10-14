import { HttpException, type Logger } from '@nestjs/common';
import { AiUpstreamError } from '../ai/ai.client';

/**
 * Translate an error from an upstream (AI service) call into an HttpException
 * with the consistent `{ code, message }` envelope. A structured
 * `AiUpstreamError` keeps its status + code; anything else (network failure,
 * timeout) is surfaced as a 503 without leaking internals.
 *
 * Shared by the controllers that proxy to the AI service so the mapping lives
 * in exactly one place.
 */
export function mapUpstreamError(err: unknown, logger?: Logger): HttpException {
  if (err instanceof AiUpstreamError) {
    return new HttpException({ code: err.code, message: err.message }, err.status);
  }
  logger?.error(
    `upstream call failed: ${err instanceof Error ? err.message : String(err)}`,
  );
  return new HttpException(
    { code: 'gateway_upstream_error', message: 'The upstream service is unavailable.' },
    503,
  );
}
