import { Inject, Injectable, Logger } from '@nestjs/common';
import type { ChatRequest, DocumentSummary } from '@veridoc/contracts';
import { CONFIG, type AppConfig } from '../config';

/**
 * Thin client for the internal AI service. Encapsulates upstream URLs,
 * timeouts, and abort handling so controllers stay declarative.
 */
@Injectable()
export class AiClient {
  private readonly logger = new Logger(AiClient.name);

  constructor(@Inject(CONFIG) private readonly config: AppConfig) {}

  /** Fetch the list of available (fixture) documents. */
  async listDocuments(): Promise<DocumentSummary[]> {
    const url = `${this.config.AI_SERVICE_URL}/v1/documents`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.config.AI_REQUEST_TIMEOUT_MS);
    try {
      const resp = await fetch(url, { signal: controller.signal });
      if (!resp.ok) {
        throw new Error(`AI service returned ${resp.status} for ${url}`);
      }
      return (await resp.json()) as DocumentSummary[];
    } finally {
      clearTimeout(timeout);
    }
  }

  /**
   * Open the upstream SSE chat stream. Returns the raw `fetch` Response so the
   * caller can pipe the body through to the browser. The provided `signal`
   * (from the caller) is combined with an internal timeout.
   */
  async openChatStream(body: ChatRequest, signal: AbortSignal): Promise<Response> {
    const url = `${this.config.AI_SERVICE_URL}/v1/chat/stream`;
    const timeoutController = new AbortController();
    const timeout = setTimeout(
      () => timeoutController.abort(new Error('AI service request timed out')),
      this.config.AI_REQUEST_TIMEOUT_MS,
    );

    // Abort upstream if either the client disconnects or the timeout fires.
    const onAbort = () => timeoutController.abort();
    signal.addEventListener('abort', onAbort, { once: true });

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify(body),
        signal: timeoutController.signal,
      });
      if (!resp.ok || !resp.body) {
        throw new Error(`AI service returned ${resp.status} for ${url}`);
      }
      // Clear the timeout once the stream has successfully opened; streaming
      // itself may legitimately outlast the connect timeout.
      clearTimeout(timeout);
      return resp;
    } catch (err) {
      clearTimeout(timeout);
      signal.removeEventListener('abort', onAbort);
      this.logger.error(`Failed to open chat stream: ${(err as Error).message}`);
      throw err;
    }
  }
}
