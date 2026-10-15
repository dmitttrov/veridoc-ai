import { randomUUID } from 'node:crypto';
import type { NextFunction, Request, Response } from 'express';
import { REQUEST_ID_HEADER, requestContext, sanitizeRequestId } from './request-context';

/**
 * Establishes the per-request correlation id: reuse a safe inbound
 * `x-request-id` (e.g. from an upstream proxy) or mint a fresh UUID, echo it on
 * the response, and run the rest of the pipeline inside the request context so
 * logs and the upstream AI call are all tagged with the same id.
 */
export function requestIdMiddleware(
  req: Request,
  res: Response,
  next: NextFunction,
): void {
  const requestId = sanitizeRequestId(req.headers[REQUEST_ID_HEADER]) ?? randomUUID();
  res.setHeader(REQUEST_ID_HEADER, requestId);
  requestContext.run({ requestId }, () => next());
}
