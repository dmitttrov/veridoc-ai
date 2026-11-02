import { useCallback, useRef, useState } from 'react';
import type { ChatMessage, Citation } from '@veridoc/contracts';
import { streamRag } from '../lib/api';

export type RagStatus = 'idle' | 'thinking' | 'streaming' | 'done' | 'error';

/** One question → verified-answer exchange in the grounded conversation. */
export interface RagTurn {
  id: string;
  question: string;
  /** The verified answer text (streamed only after citation validation). */
  answer: string;
  citations: Citation[];
  abstained: boolean;
  invalidCitationCount: number;
  mock: boolean | null;
  model: string | null;
  status: Exclude<RagStatus, 'idle'>;
  error: string | null;
}

export interface UseRag {
  turns: RagTurn[];
  /** Status of the latest turn, or 'idle' before the first question. */
  status: RagStatus;
  /** Mock/model identity from the most recent completed turn. */
  mock: boolean | null;
  model: string | null;
  error: string | null;
  ask: (question: string, documentIds: string[]) => Promise<void>;
  reset: () => void;
}

/** Contract bounds (RagRequestSchema): ≤50 history messages of ≤8000 chars. */
const MAX_HISTORY_MESSAGES = 50;
const MAX_MESSAGE_CHARS = 8000;

let turnCounter = 0;
const nextId = (): string => `rag-turn-${++turnCounter}`;

/**
 * Serialize completed turns into wire history. Errored/aborted turns carry no
 * answer and are skipped entirely — a question the system never answered adds
 * no interpretable context.
 */
function toHistory(turns: RagTurn[]): ChatMessage[] {
  const messages: ChatMessage[] = [];
  for (const t of turns) {
    if (t.status !== 'done' || !t.question.trim() || !t.answer.trim()) continue;
    messages.push({ role: 'user', content: t.question.slice(0, MAX_MESSAGE_CHARS) });
    messages.push({ role: 'assistant', content: t.answer.slice(0, MAX_MESSAGE_CHARS) });
  }
  // Keep the most recent messages; slice an even count so pairs stay intact.
  return messages.slice(-MAX_HISTORY_MESSAGES);
}

export function useRag(): UseRag {
  const [turns, setTurns] = useState<RagTurn[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const last = turns.length > 0 ? turns[turns.length - 1] : null;
  const status: RagStatus = last?.status ?? 'idle';
  const lastDone = [...turns].reverse().find((t) => t.status === 'done') ?? null;

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setTurns([]);
  }, []);

  const ask = useCallback(
    async (question: string, documentIds: string[]): Promise<void> => {
      const trimmed = question.trim();
      if (!trimmed || status === 'thinking' || status === 'streaming') return;

      abortRef.current?.abort();
      const abort = new AbortController();
      abortRef.current = abort;

      const id = nextId();
      const history = toHistory(turns);
      // The AI service buffers + verifies before the first token, so there is
      // a genuine "thinking" phase before "streaming".
      setTurns((prev) => [
        ...prev,
        {
          id,
          question: trimmed,
          answer: '',
          citations: [],
          abstained: false,
          invalidCitationCount: 0,
          mock: null,
          model: null,
          status: 'thinking',
          error: null,
        },
      ]);

      const update = (fn: (turn: RagTurn) => RagTurn): void => {
        setTurns((prev) => prev.map((t) => (t.id === id ? fn(t) : t)));
      };

      try {
        for await (const event of streamRag(
          { question: trimmed, history, documentIds, topK: 5 },
          abort.signal,
        )) {
          switch (event.type) {
            case 'token':
              update((t) => ({
                ...t,
                status: 'streaming',
                answer: t.answer + event.text,
              }));
              break;
            case 'citations':
              update((t) => ({ ...t, citations: event.citations }));
              break;
            case 'done':
              update((t) => ({
                ...t,
                status: 'done',
                mock: event.mock,
                model: event.model,
                abstained: event.abstained ?? false,
                invalidCitationCount: event.invalidCitationCount ?? 0,
              }));
              break;
            case 'error':
              update((t) => ({ ...t, status: 'error', error: event.message }));
              break;
          }
        }
      } catch (err) {
        if (abort.signal.aborted) return;
        update((t) => ({
          ...t,
          status: 'error',
          error: err instanceof Error ? err.message : 'Request failed',
        }));
      } finally {
        if (abortRef.current === abort) abortRef.current = null;
      }
    },
    [status, turns],
  );

  return {
    turns,
    status,
    mock: lastDone?.mock ?? null,
    model: lastDone?.model ?? null,
    error: last?.status === 'error' ? last.error : null,
    ask,
    reset,
  };
}
