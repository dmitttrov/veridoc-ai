import { useState, type FormEvent } from 'react';
import type { ChatTurn, ChatStatus } from '../hooks/useChat';
import { cx } from '../lib/cx';
import styles from '../styles.module.css';

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
    <section className={cx(styles.panel, styles.chat)} aria-labelledby="chat-heading">
      <h2 id="chat-heading">Conversation</h2>

      <div
        className={styles.messages}
        role="log"
        aria-live="polite"
        aria-relevant="additions text"
      >
        {turns.length === 0 && (
          <p className={styles.hint}>
            Ask a question about the selected documents to get started.
          </p>
        )}
        {turns.map((turn) => (
          <article
            key={turn.id}
            className={cx(styles.message, turn.role === 'user' && styles['message-user'])}
          >
            <span className={styles['message-role']}>
              {turn.role === 'user' ? 'You' : 'Veridoc'}
            </span>
            <div className={styles['message-content']}>
              {turn.content}
              {turn.pending && (
                <span className={styles.cursor} aria-hidden="true">
                  ▋
                </span>
              )}
            </div>
            {turn.citations && turn.citations.length > 0 && (
              <ul className={styles.citations}>
                {turn.citations.map((c, i) => (
                  <li key={`${turn.id}-cite-${i}`} className={styles.citation}>
                    <span className={styles['citation-source']}>
                      {c.documentTitle} — p.{c.page}
                    </span>
                    <span className={styles['citation-snippet']}>“{c.snippet}”</span>
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>

      <form className={styles.composer} onSubmit={submit}>
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
          <button type="button" onClick={onStop} className={styles.secondary}>
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
