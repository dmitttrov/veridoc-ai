import { useState, type FormEvent } from 'react';
import { useRetrieval } from '../hooks/useRetrieval';
import styles from '../styles.module.css';
import { DocumentsPanel } from './DocumentsPanel';

export function RetrievalView() {
  const {
    stored,
    storedError,
    selectedIds,
    toggle,
    uploadStatus,
    uploadResult,
    uploadError,
    upload,
    retrievalStatus,
    response,
    retrievalError,
    runRetrieval,
  } = useRetrieval();

  const [query, setQuery] = useState('');

  const submitQuery = (e: FormEvent): void => {
    e.preventDefault();
    void runRetrieval(query);
  };

  return (
    <div className={styles.layout}>
      <DocumentsPanel
        stored={stored}
        storedError={storedError}
        selectedIds={selectedIds}
        onToggle={toggle}
        uploadStatus={uploadStatus}
        uploadResult={uploadResult}
        uploadError={uploadError}
        onUpload={upload}
        hint="Select documents to scope retrieval (optional)."
      />

      <section
        className={`${styles.panel} ${styles.chat}`}
        aria-labelledby="retrieval-heading"
      >
        <h2 id="retrieval-heading">Retrieved evidence</h2>
        <p className={styles['evidence-disclaimer']}>
          These are <strong>source passages retrieved from your documents</strong> —
          verbatim excerpts with page citations. They are <strong>not</strong> an
          AI-generated answer or conclusion.
        </p>

        <form className={styles.composer} onSubmit={submitQuery}>
          <label htmlFor="retrieval-input" className="sr-only">
            Question
          </label>
          <input
            id="retrieval-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. What was total revenue in FY2023?"
            disabled={retrievalStatus === 'loading'}
          />
          <button type="submit" disabled={!query.trim() || retrievalStatus === 'loading'}>
            {retrievalStatus === 'loading' ? 'Searching…' : 'Find evidence'}
          </button>
        </form>

        {retrievalError && (
          <p role="alert" className={styles.error}>
            {retrievalError}
          </p>
        )}

        {response && (
          <div className={styles.passages} aria-live="polite">
            <p className={styles.hint}>
              {response.passages.length} passage(s) · embedding model{' '}
              <code>{response.embeddingModel}</code>
              {response.reranked && (
                <>
                  {' '}
                  · reranked by <code>{response.rerankerModel}</code>
                </>
              )}
            </p>
            {response.passages.length === 0 && (
              <p className={styles.hint}>
                No matching evidence found in the selected documents.
              </p>
            )}
            {response.passages.map((p) => (
              <article key={p.chunkId} className={styles.passage}>
                <header className={styles['passage-head']}>
                  <button
                    type="button"
                    className={styles['citation-link']}
                    title={`${p.documentTitle} — page ${p.page}, characters ${p.charStart}–${p.charEnd}`}
                  >
                    {p.citation}
                  </button>
                  <span className={styles['passage-scores']}>
                    lex {p.scores.lexical.toFixed(3)} · sem {p.scores.semantic.toFixed(3)}{' '}
                    · fused {p.scores.fused.toFixed(4)}
                    {p.scores.rerank != null && (
                      <> · rerank {p.scores.rerank.toFixed(3)}</>
                    )}
                  </span>
                </header>
                <blockquote className={styles['passage-text']}>{p.text}</blockquote>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
