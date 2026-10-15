import { Inject, Injectable, Logger } from '@nestjs/common';
import {
  type ChatRequest,
  type DocumentIngestionResult,
  DocumentIngestionResultSchema,
  type DocumentSummary,
  DocumentSummarySchema,
  type RagRequest,
  type RetrievalRequest,
  type RetrievalResponse,
  RetrievalResponseSchema,
  type StoredDocument,
  StoredDocumentSchema,
} from '@veridoc/contracts';
import { z } from 'zod';
import { REQUEST_ID_HEADER, getRequestId } from '../common/request-context';
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

  /** Merge the current request's correlation id into outbound headers so the AI
   * service logs the same id (end-to-end tracing across the hop). */
  private outboundHeaders(base: Record<string, string> = {}): Record<string, string> {
    const id = getRequestId();
    return id ? { ...base, [REQUEST_ID_HEADER]: id } : base;
  }

  /**
   * Validate an upstream JSON payload against the shared contract. The AI
   * service is trusted, but a shape mismatch means a contract drift or a bug —
   * surface it as a 502-class error rather than forwarding malformed data.
   */
  private parse<T>(data: unknown, schema: z.ZodType<T>): T {
    const result = schema.safeParse(data);
    if (!result.success) {
      this.logger.error(`upstream response failed validation: ${result.error.message}`);
      throw new AiUpstreamError(
        502,
        'ai_invalid_response',
        'The AI service returned an unexpected response.',
      );
    }
    return result.data;
  }

  /**
   * Probe the AI service's readiness endpoint with a short timeout. Used by the
   * gateway's own `/ready` probe so an orchestrator sees the gateway as
   * not-ready when its only upstream cannot serve. Never throws: a failed probe
   * (timeout, connection refused, 503) resolves to `{ ready: false }`.
   */
  async checkReady(): Promise<{ ready: boolean }> {
    const url = `${this.config.AI_SERVICE_URL}/readyz`;
    const controller = new AbortController();
    const timeout = setTimeout(
      () => controller.abort(),
      this.config.AI_HEALTH_TIMEOUT_MS,
    );
    try {
      const resp = await fetch(url, {
        headers: this.outboundHeaders(),
        signal: controller.signal,
      });
      return { ready: resp.ok };
    } catch {
      return { ready: false };
    } finally {
      clearTimeout(timeout);
    }
  }

  /** Fetch the list of available (fixture) documents. */
  async listDocuments(): Promise<DocumentSummary[]> {
    const url = `${this.config.AI_SERVICE_URL}/v1/documents`;
    const resp = await this.getJson(url);
    return this.parse(await resp.json(), z.array(DocumentSummarySchema));
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
        headers: this.outboundHeaders(),
        signal: controller.signal,
      });
      if (!resp.ok) {
        throw await this.toUpstreamError(resp, url);
      }
      return this.parse(await resp.json(), DocumentIngestionResultSchema);
    } finally {
      clearTimeout(timeout);
    }
  }

  /** List documents that have been ingested and stored. */
  async listStoredDocuments(): Promise<StoredDocument[]> {
    const url = `${this.config.AI_SERVICE_URL}/v1/documents/stored`;
    const resp = await this.getJson(url);
    return this.parse(await resp.json(), z.array(StoredDocumentSchema));
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
        headers: this.outboundHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!resp.ok) {
        throw await this.toUpstreamError(resp, url);
      }
      return this.parse(await resp.json(), RetrievalResponseSchema);
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
      const resp = await fetch(url, {
        headers: this.outboundHeaders(),
        signal: controller.signal,
      });
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
      const body = (await resp.json()) as {
        detail?: { code?: string; message?: string };
      };
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
    return this.openStream('/v1/chat/stream', body, signal);
  }

  /**
   * Open the upstream grounded-RAG SSE stream. The AI service buffers and
   * verifies citations before emitting; the gateway pipes the verified bytes.
   */
  async openRagStream(body: RagRequest, signal: AbortSignal): Promise<Response> {
    return this.openStream('/v1/rag/answer', body, signal);
  }

  private async openStream(
    path: string,
    body: unknown,
    signal: AbortSignal,
  ): Promise<Response> {
    const url = `${this.config.AI_SERVICE_URL}${path}`;
    const timeoutController = new AbortController();
    // RAG buffers a full generation before streaming, so use the longer
    // ingest-class timeout for it; plain chat uses the request timeout.
    const timeoutMs =
      path === '/v1/rag/answer'
        ? this.config.AI_INGEST_TIMEOUT_MS
        : this.config.AI_REQUEST_TIMEOUT_MS;
    const timeout = setTimeout(
      () => timeoutController.abort(new Error('AI service request timed out')),
      timeoutMs,
    );

    // Abort upstream if either the client disconnects or the timeout fires.
    const onAbort = () => timeoutController.abort();
    signal.addEventListener('abort', onAbort, { once: true });

    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: this.outboundHeaders({
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        }),
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
      this.logger.error(`Failed to open stream ${path}: ${(err as Error).message}`);
      throw err;
    }
  }
}
