import { AsyncLocalStorage } from 'node:async_hooks';

/** Per-request ambient context, propagated across async boundaries so that the
 * singleton AiClient, the exception filter, and the logger can all see the same
 * correlation id without threading it through every call. */
export interface RequestContext {
  requestId: string;
}

export const requestContext = new AsyncLocalStorage<RequestContext>();

/** The canonical correlation header, echoed to clients and forwarded upstream. */
export const REQUEST_ID_HEADER = 'x-request-id';

/** The current request's correlation id, if we are within a request scope. */
export function getRequestId(): string | undefined {
  return requestContext.getStore()?.requestId;
}

/**
 * Accept an inbound id only if it is a short, safe token — this value is logged
 * and reflected in a response header, so reject anything that could be used for
 * log forging or header injection; the caller generates a fresh id instead.
 */
export function sanitizeRequestId(value: unknown): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  if (typeof raw !== 'string') return undefined;
  const trimmed = raw.trim();
  if (trimmed.length === 0 || trimmed.length > 128) return undefined;
  return /^[A-Za-z0-9._-]+$/.test(trimmed) ? trimmed : undefined;
}
