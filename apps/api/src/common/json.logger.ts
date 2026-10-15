import type { LoggerService, LogLevel } from '@nestjs/common';
import { getRequestId } from './request-context';

/**
 * Minimal structured (one-JSON-object-per-line) logger for production. Every
 * line carries the current request's correlation id (when in a request scope),
 * so gateway logs can be joined to the AI service's logs for the same request.
 * Development keeps Nest's pretty console logger for readability.
 */
export class JsonLogger implements LoggerService {
  private write(
    level: LogLevel,
    message: unknown,
    context?: string,
    extra?: Record<string, unknown>,
  ): void {
    const entry = {
      time: new Date().toISOString(),
      level,
      context,
      requestId: getRequestId(),
      message: typeof message === 'string' ? message : JSON.stringify(message),
      ...extra,
    };
    const line = `${JSON.stringify(entry)}\n`;
    if (level === 'error') process.stderr.write(line);
    else process.stdout.write(line);
  }

  log(message: unknown, context?: string): void {
    this.write('log', message, context);
  }

  error(message: unknown, stack?: string, context?: string): void {
    this.write('error', message, context, stack ? { stack } : undefined);
  }

  warn(message: unknown, context?: string): void {
    this.write('warn', message, context);
  }

  debug(message: unknown, context?: string): void {
    this.write('debug', message, context);
  }

  verbose(message: unknown, context?: string): void {
    this.write('verbose', message, context);
  }
}
