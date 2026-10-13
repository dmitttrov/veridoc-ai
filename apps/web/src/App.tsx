import { useCallback, useEffect, useState } from 'react';
import type { DocumentSummary } from '@veridoc/contracts';
import { ChatPanel } from './components/ChatPanel';
import { DocumentList } from './components/DocumentList';
import { RetrievalView } from './components/RetrievalView';
import { useChat } from './hooks/useChat';
import { fetchDocuments } from './lib/api';

type Mode = 'retrieval' | 'chat';

export function App() {
  const [mode, setMode] = useState<Mode>('retrieval');

  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [docsError, setDocsError] = useState<string | null>(null);

  const { turns, status, error, mockMode, send, stop } = useChat();

  useEffect(() => {
    const controller = new AbortController();
    fetchDocuments(controller.signal)
      .then((docs) => {
        setDocuments(docs);
        setDocsError(null);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setDocsError(err instanceof Error ? err.message : 'Failed to load documents');
      })
      .finally(() => {
        if (!controller.signal.aborted) setDocsLoading(false);
      });
    return () => controller.abort();
  }, []);

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
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <h1>Veridoc AI</h1>
          <span className="tagline">Source-grounded financial document intelligence</span>
        </div>
        <div className="header-right">
          <div className="mode-switch" role="tablist" aria-label="View mode">
            <button
              role="tab"
              aria-selected={mode === 'retrieval'}
              className={mode === 'retrieval' ? 'active' : ''}
              onClick={() => setMode('retrieval')}
            >
              Document Retrieval
            </button>
            <button
              role="tab"
              aria-selected={mode === 'chat'}
              className={mode === 'chat' ? 'active' : ''}
              onClick={() => setMode('chat')}
            >
              Mock Chat
            </button>
          </div>
          {mode === 'chat' && mockMode !== false && (
            <span
              className="mock-badge"
              title="Responses are produced by a deterministic mock, not a real model."
            >
              MOCK MODE
            </span>
          )}
        </div>
      </header>

      {mode === 'chat' && error && (
        <div role="alert" className="banner banner-error">
          {error}
        </div>
      )}

      <main>
        {mode === 'retrieval' ? (
          <RetrievalView />
        ) : (
          <div className="layout">
            <DocumentList
              documents={documents}
              selectedIds={selectedIds}
              loading={docsLoading}
              error={docsError}
              onToggle={toggleDocument}
            />
            <ChatPanel turns={turns} status={status} onSend={onSend} onStop={stop} />
          </div>
        )}
      </main>

      <footer className="app-footer">
        <span>
          {mode === 'retrieval'
            ? 'Phase 2 · real PDF ingestion + hybrid retrieval · evidence only, no generated answers.'
            : 'Phase 1 vertical slice · deterministic mock inference · no real financial data.'}
        </span>
      </footer>
    </div>
  );
}
