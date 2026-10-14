/** Centralized, validated runtime configuration (env-driven, no secrets). */
import { z } from 'zod';

const EnvSchema = z.object({
  /** Gateway listen port. 0 is allowed and means "let the OS assign a port". */
  PORT: z.coerce.number().int().nonnegative().max(65535).default(3000),
  /** Internal AI service base URL. Never exposed to the browser. */
  AI_SERVICE_URL: z.string().url().default('http://127.0.0.1:8000'),
  /** Allowed browser origin for CORS (the web app). */
  WEB_ORIGIN: z.string().url().default('http://localhost:5173'),
  /** Upstream request timeout for the AI service, in milliseconds. */
  AI_REQUEST_TIMEOUT_MS: z.coerce.number().int().positive().default(30000),
  /** Longer timeout for document ingestion (parsing + embedding). */
  AI_INGEST_TIMEOUT_MS: z.coerce.number().int().positive().default(120000),
  /** Rate-limit window (ms) and max requests per window per client IP. */
  RATE_LIMIT_TTL_MS: z.coerce.number().int().positive().default(60000),
  RATE_LIMIT_MAX: z.coerce.number().int().positive().default(100),
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
});

export type AppConfig = z.infer<typeof EnvSchema>;

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  // Treat empty-string env vars as unset so schema defaults apply. Without this,
  // `PORT=` (empty) coerces to 0 and fails validation instead of defaulting.
  const cleaned = Object.fromEntries(
    Object.entries(env).filter(([, v]) => v !== undefined && v !== ''),
  );
  const parsed = EnvSchema.safeParse(cleaned);
  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((i) => `${i.path.join('.')}: ${i.message}`)
      .join('; ');
    throw new Error(`Invalid environment configuration: ${issues}`);
  }
  return parsed.data;
}

export const CONFIG = Symbol('APP_CONFIG');
