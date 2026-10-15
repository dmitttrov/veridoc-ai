import { useCallback, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChatPanel } from './components/ChatPanel';
import { DocumentList } from './components/DocumentList';
import { RagView } from './components/RagView';
import { RetrievalView } from './components/RetrievalView';
import { useChat } from './hooks/useChat';
import { cx } from './lib/cx';
import { fetchDocuments } from './lib/api';
import styles from './styles.module.css';

type Mode = 'rag' | 'retrieval' | 'chat';

export function App() {
  const [mode, setMode] = useState<Mode>('rag');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // React Query owns the fetch lifecycle (caching, dedup, and request
  // cancellation via the injected AbortSignal).
  const documentsQuery = useQuery({
    queryKey: ['documents'],
    queryFn: ({ signal }) => fetchDocuments(signal),
  });
  const documents = documentsQuery.data ?? [];
  const docsError = documentsQuery.isError
    ? documentsQuery.error instanceof Error
      ? documentsQuery.error.message
      : 'Failed to load documents'
    : null;

  const { turns, status, error, mockMode, send, stop } = useChat();

  const toggleDocument = useCallback((id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }, []);

  const onSend = useCallback(
    (message: string) => {
      void send(message, selectedIds);
    },
    [send, selectedIds],
  );

  return (
    <div className={styles.app}>
      <header className={styles['app-header']}>
        <div className={styles.brand}>
          <h1>Veridoc AI</h1>
          <span className={styles.tagline}>
            Source-grounded financial document intelligence
          </span>
        </div>
        <div className={styles['header-right']}>
          <div className={styles['mode-switch']} role="tablist" aria-label="View mode">
            <button
              role="tab"
              aria-selected={mode === 'rag'}
              className={mode === 'rag' ? styles.active : ''}
              onClick={() => setMode('rag')}
            >
              Grounded Answer
            </button>
            <button
              role="tab"
              aria-selected={mode === 'retrieval'}
              className={mode === 'retrieval' ? styles.active : ''}
              onClick={() => setMode('retrieval')}
            >
              Retrieval
            </button>
            <button
              role="tab"
              aria-selected={mode === 'chat'}
              className={mode === 'chat' ? styles.active : ''}
              onClick={() => setMode('chat')}
            >
              Mock Chat
            </button>
          </div>
          {mode === 'chat' && mockMode !== false && (
            <span
              className={styles['mock-badge']}
              title="Responses are produced by a deterministic mock, not a real model."
            >
              MOCK MODE
            </span>
          )}
        </div>
      </header>

      {mode === 'chat' && error && (
        <div role="alert" className={cx(styles.banner, styles['banner-error'])}>
          {error}
        </div>
      )}

      <main>
        {mode === 'rag' && <RagView />}
        {mode === 'retrieval' && <RetrievalView />}
        {mode === 'chat' && (
          <div className={styles.layout}>
            <DocumentList
              documents={documents}
              selectedIds={selectedIds}
              loading={documentsQuery.isLoading}
              error={docsError}
              onToggle={toggleDocument}
            />
            <ChatPanel turns={turns} status={status} onSend={onSend} onStop={stop} />
          </div>
        )}
      </main>

      <footer className={styles['app-footer']}>
        <span>
          {mode === 'rag' &&
            'Phase 3 · grounded RAG · hybrid retrieval + reranking + verified citations · model not fine-tuned.'}
          {mode === 'retrieval' &&
            'Phase 2 · hybrid retrieval · evidence only, no generated answers.'}
          {mode === 'chat' &&
            'Phase 1 · deterministic mock chat · no real financial data.'}
        </span>
      </footer>
    </div>
  );
}
