import {
  type ArgumentsHost,
  Catch,
  type ExceptionFilter,
  HttpException,
  Logger,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import { AiUpstreamError } from '../ai/ai.client';

/** A stable error code to attach when an HttpException carries only a status. */
function codeForStatus(status: number): string {
  switch (status) {
    case 400:
      return 'invalid_request';
    case 401:
      return 'unauthorized';
    case 403:
      return 'forbidden';
    case 404:
      return 'not_found';
    case 413:
      return 'payload_too_large';
    case 415:
      return 'unsupported_media_type';
    case 429:
      return 'rate_limited';
    case 503:
      return 'service_unavailable';
    default:
      return status >= 500 ? 'internal_error' : 'request_error';
  }
}

interface ErrorBody {
  code: string;
  message: string;
  issues?: unknown;
}

/**
 * Single place that shapes every error into a consistent `{ code, message }`
 * envelope (optionally with `issues` for validation errors). Unexpected errors
 * become an opaque 500 so internals never leak. Mid-stream SSE failures are
 * left to the controller — once headers are sent we only close the socket.
 */
@Catch()
export class AllExceptionsFilter implements ExceptionFilter {
  private readonly logger = new Logger(AllExceptionsFilter.name);

  catch(exception: unknown, host: ArgumentsHost): void {
    const ctx = host.switchToHttp();
    const res = ctx.getResponse<Response>();
    const req = ctx.getRequest<Request>();

    // A streaming response is already in flight (its controller owns terminal
    // error events); we cannot replace it with a JSON body.
    if (res.headersSent) {
      if (!res.writableEnded) res.end();
      return;
    }

    let status = 500;
    let body: ErrorBody = { code: 'internal_error', message: 'Internal server error' };

    if (exception instanceof AiUpstreamError) {
      status = exception.status;
      body = { code: exception.code, message: exception.message };
    } else if (exception instanceof HttpException) {
      status = exception.getStatus();
      const resp = exception.getResponse();
      if (typeof resp === 'string') {
        body = { code: codeForStatus(status), message: resp };
      } else {
        const o = resp as Record<string, unknown>;
        const message =
          typeof o.message === 'string'
            ? o.message
            : Array.isArray(o.message)
              ? o.message.join('; ')
              : exception.message;
        body = {
          code: typeof o.code === 'string' ? o.code : codeForStatus(status),
          message,
          ...(o.issues !== undefined ? { issues: o.issues } : {}),
        };
      }
    }

    // Only 5xx are unexpected enough to log; 4xx are normal client errors.
    if (status >= 500) {
      const detail = exception instanceof Error ? exception.message : String(exception);
      this.logger.error(`${req.method} ${req.originalUrl} -> ${status}: ${detail}`);
    }

    res.status(status).json(body);
  }
}
