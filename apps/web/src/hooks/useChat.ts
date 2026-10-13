import { useCallback, useRef, useState } from 'react';
import type { Citation } from '@veridoc/contracts';
import { streamChat } from '../lib/api';

export interface ChatTurn {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  /** Citations attached to an assistant turn once the stream completes. */
  citations?: Citation[];
  /** True while this assistant turn is still streaming. */
  pending?: boolean;
}

export type ChatStatus = 'idle' | 'streaming' | 'error';

export interface UseChat {
  turns: ChatTurn[];
  status: ChatStatus;
  error: string | null;
  /** Null until the first completed answer reveals whether mock mode is active. */
  mockMode: boolean | null;
  send: (message: string, documentIds: string[]) => Promise<void>;
  stop: () => void;
}

let turnCounter = 0;
const nextId = (): string => `turn-${++turnCounter}`;

export function useChat(): UseChat {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [status, setStatus] = useState<ChatStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [mockMode, setMockMode] = useState<boolean | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus('idle');
    setTurns((prev) =>
      prev.map((t) => (t.pending ? { ...t, pending: false } : t)),
    );
  }, []);

  const send = useCallback(
    async (message: string, documentIds: string[]): Promise<void> => {
      const trimmed = message.trim();
      if (!trimmed || status === 'streaming') return;

      setError(null);
      setStatus('streaming');

      const assistantId = nextId();
      setTurns((prev) => [
        ...prev,
        { id: nextId(), role: 'user', content: trimmed },
        { id: assistantId, role: 'assistant', content: '', pending: true },
      ]);

      const updateAssistant = (fn: (turn: ChatTurn) => ChatTurn): void => {
        setTurns((prev) => prev.map((t) => (t.id === assistantId ? fn(t) : t)));
      };

      const abort = new AbortController();
      abortRef.current = abort;

      try {
        for await (const event of streamChat(
          { message: trimmed, history: [], documentIds },
          abort.signal,
        )) {
          switch (event.type) {
            case 'token':
              updateAssistant((t) => ({ ...t, content: t.content + event.text }));
              break;
            case 'citations':
              updateAssistant((t) => ({ ...t, citations: event.citations }));
              break;
            case 'done':
              setMockMode(event.mock);
              updateAssistant((t) => ({ ...t, pending: false }));
              setStatus('idle');
              break;
            case 'error':
              setError(event.message);
              updateAssistant((t) => ({
                ...t,
                pending: false,
                content: t.content || '(no response)',
              }));
              setStatus('error');
              break;
          }
        }
      } catch (err) {
        if (abort.signal.aborted) return;
        setError(err instanceof Error ? err.message : 'Unexpected error');
        updateAssistant((t) => ({ ...t, pending: false }));
        setStatus('error');
      } finally {
        if (abortRef.current === abort) abortRef.current = null;
      }
    },
    [status],
  );

  return { turns, status, error, mockMode, send, stop };
}
