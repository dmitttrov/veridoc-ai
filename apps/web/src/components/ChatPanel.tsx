import { useState, type FormEvent } from 'react';
import type { ChatTurn, ChatStatus } from '../hooks/useChat';

interface Props {
  turns: ChatTurn[];
  status: ChatStatus;
  onSend: (message: string) => void;
  onStop: () => void;
}

export function ChatPanel({ turns, status, onSend, onStop }: Props) {
  const [draft, setDraft] = useState('');
  const streaming = status === 'streaming';

  const submit = (e: FormEvent): void => {
    e.preventDefault();
    const message = draft.trim();
    if (!message || streaming) return;
    onSend(message);
    setDraft('');
  };

  return (
    <section className="panel chat" aria-labelledby="chat-heading">
      <h2 id="chat-heading">Conversation</h2>

      <div className="messages" role="log" aria-live="polite" aria-relevant="additions text">
        {turns.length === 0 && (
          <p className="hint">
            Ask a question about the selected documents to get started.
          </p>
        )}
        {turns.map((turn) => (
          <article key={turn.id} className={`message message-${turn.role}`}>
            <span className="message-role">{turn.role === 'user' ? 'You' : 'Veridoc'}</span>
            <div className="message-content">
              {turn.content}
              {turn.pending && <span className="cursor" aria-hidden="true">▋</span>}
            </div>
            {turn.citations && turn.citations.length > 0 && (
              <ul className="citations">
                {turn.citations.map((c, i) => (
                  <li key={`${turn.id}-cite-${i}`} className="citation">
                    <span className="citation-source">
                      {c.documentTitle} — p.{c.page}
                    </span>
                    <span className="citation-snippet">“{c.snippet}”</span>
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>

      <form className="composer" onSubmit={submit}>
        <label htmlFor="chat-input" className="sr-only">
          Your question
        </label>
        <textarea
          id="chat-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) submit(e);
          }}
          placeholder="e.g. What was total revenue for FY2023?"
          rows={2}
          disabled={streaming}
        />
        {streaming ? (
          <button type="button" onClick={onStop} className="secondary">
            Stop
          </button>
        ) : (
          <button type="submit" disabled={!draft.trim()}>
            Send
          </button>
        )}
      </form>
    </section>
  );
}
