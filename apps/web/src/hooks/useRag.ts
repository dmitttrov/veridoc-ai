import { useCallback, useRef, useState } from 'react';
import type { Citation } from '@veridoc/contracts';
import { streamRag } from '../lib/api';

export type RagStatus = 'idle' | 'thinking' | 'streaming' | 'done' | 'error';

export interface RagState {
  status: RagStatus;
  /** The verified answer text (streamed only after citation validation). */
  answer: string;
  citations: Citation[];
  abstained: boolean;
  invalidCitationCount: number;
  /** Null until the first answer reveals whether a mock produced it. */
  mock: boolean | null;
  model: string | null;
  error: string | null;
}

export interface UseRag extends RagState {
  ask: (question: string, documentIds: string[]) => Promise<void>;
  reset: () => void;
}

const INITIAL: RagState = {
  status: 'idle',
  answer: '',
  citations: [],
  abstained: false,
  invalidCitationCount: 0,
  mock: null,
  model: null,
  error: null,
};

export function useRag(): UseRag {
  const [state, setState] = useState<RagState>(INITIAL);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState(INITIAL);
  }, []);

  const ask = useCallback(
    async (question: string, documentIds: string[]): Promise<void> => {
      const trimmed = question.trim();
      if (!trimmed || state.status === 'thinking' || state.status === 'streaming') return;

      abortRef.current?.abort();
      const abort = new AbortController();
      abortRef.current = abort;

      // The AI service buffers + verifies before the first token, so there is a
      // genuine "thinking" phase before "streaming".
      setState({ ...INITIAL, status: 'thinking' });

      try {
        for await (const event of streamRag(
          { question: trimmed, documentIds, topK: 5 },
          abort.signal,
        )) {
          switch (event.type) {
            case 'token':
              setState((s) => ({
                ...s,
                status: 'streaming',
                answer: s.answer + event.text,
              }));
              break;
            case 'citations':
              setState((s) => ({ ...s, citations: event.citations }));
              break;
            case 'done':
              setState((s) => ({
                ...s,
                status: 'done',
                mock: event.mock,
                model: event.model,
                abstained: event.abstained ?? false,
                invalidCitationCount: event.invalidCitationCount ?? 0,
              }));
              break;
            case 'error':
              setState((s) => ({ ...s, status: 'error', error: event.message }));
              break;
          }
        }
      } catch (err) {
        if (abort.signal.aborted) return;
        setState((s) => ({
          ...s,
          status: 'error',
          error: err instanceof Error ? err.message : 'Request failed',
        }));
      } finally {
        if (abortRef.current === abort) abortRef.current = null;
      }
    },
    [state.status],
  );

  return { ...state, ask, reset };
}
