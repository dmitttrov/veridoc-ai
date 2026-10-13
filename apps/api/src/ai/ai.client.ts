import { Inject, Injectable, Logger } from '@nestjs/common';
import type {
  ChatRequest,
  DocumentIngestionResult,
  DocumentSummary,
  RetrievalRequest,
  RetrievalResponse,
  StoredDocument,
} from '@veridoc/contracts';
import { CONFIG, type AppConfig } from '../config';

/** A structured upstream error with a stable code and an HTTP status to mirror. */
export class AiUpstreamError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = 'AiUpstreamError';
  }
}

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

  /** Forward an uploaded PDF to the internal AI service for ingestion. */
  async ingestDocument(
    file: Buffer,
    filename: string,
    mimeType: string,
  ): Promise<DocumentIngestionResult> {
    const url = `${this.config.AI_SERVICE_URL}/v1/documents/ingest`;
    const form = new FormData();
    form.append('file', new Blob([new Uint8Array(file)], { type: mimeType }), filename);

    const controller = new AbortController();
    const timeout = setTimeout(
      () => controller.abort(),
      this.config.AI_INGEST_TIMEOUT_MS,
    );
    try {
      const resp = await fetch(url, {
        method: 'POST',
        body: form,
        signal: controller.signal,
      });
      if (!resp.ok) {
        throw await this.toUpstreamError(resp, url);
      }
      return (await resp.json()) as DocumentIngestionResult;
    } finally {
      clearTimeout(timeout);
    }
  }

  /** List documents that have been ingested and stored. */
  async listStoredDocuments(): Promise<StoredDocument[]> {
    const url = `${this.config.AI_SERVICE_URL}/v1/documents/stored`;
    const resp = await this.getJson(url);
    return (await resp.json()) as StoredDocument[];
  }

  /** Run hybrid retrieval and return source passages (evidence). */
  async retrieve(body: RetrievalRequest): Promise<RetrievalResponse> {
    const url = `${this.config.AI_SERVICE_URL}/v1/retrieve`;
    const controller = new AbortController();
    const timeout = setTimeout(
      () => controller.abort(),
      this.config.AI_REQUEST_TIMEOUT_MS,
    );
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!resp.ok) {
        throw await this.toUpstreamError(resp, url);
      }
      return (await resp.json()) as RetrievalResponse;
    } finally {
      clearTimeout(timeout);
    }
  }

  private async getJson(url: string): Promise<Response> {
    const controller = new AbortController();
    const timeout = setTimeout(
      () => controller.abort(),
      this.config.AI_REQUEST_TIMEOUT_MS,
    );
    try {
      const resp = await fetch(url, { signal: controller.signal });
      if (!resp.ok) {
        throw await this.toUpstreamError(resp, url);
      }
      return resp;
    } finally {
      clearTimeout(timeout);
    }
  }

  /** Translate a non-2xx upstream response into a structured error, preserving
   * the AI service's `{code, message}` detail when present (never its body text
   * verbatim, which could contain document content). */
  private async toUpstreamError(resp: Response, url: string): Promise<AiUpstreamError> {
    let code = 'ai_upstream_error';
    let message = `AI service returned ${resp.status}`;
    try {
      const body = (await resp.json()) as { detail?: { code?: string; message?: string } };
      if (body?.detail?.code) code = body.detail.code;
      if (body?.detail?.message) message = body.detail.message;
    } catch {
      // non-JSON error body; keep defaults
    }
    this.logger.warn(`upstream ${resp.status} (${code}) for ${url}`);
    return new AiUpstreamError(resp.status, code, message);
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
