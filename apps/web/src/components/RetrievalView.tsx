import { useRef, useState, type FormEvent } from 'react';
import { useRetrieval } from '../hooks/useRetrieval';

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
  const fileInputRef = useRef<HTMLInputElement>(null);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const file = e.target.files?.[0];
    if (file) void upload(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const submitQuery = (e: FormEvent): void => {
    e.preventDefault();
    void runRetrieval(query);
  };

  return (
    <div className="layout">
      <section className="panel documents" aria-labelledby="ingest-heading">
        <h2 id="ingest-heading">Documents</h2>

        <div className="upload">
          <label className="upload-label">
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              onChange={onFileChange}
              disabled={uploadStatus === 'uploading'}
            />
          </label>
          {uploadStatus === 'uploading' && (
            <p role="status" className="hint">
              Ingesting… parsing, chunking, and embedding.
            </p>
          )}
          {uploadStatus === 'done' && uploadResult && (
            <p role="status" className="ingest-ok">
              {uploadResult.alreadyIngested
                ? `Already ingested (${uploadResult.pageCount} pages, ${uploadResult.chunkCount} chunks).`
                : `Ingested: ${uploadResult.pageCount} pages, ${uploadResult.chunkCount} chunks.`}
            </p>
          )}
          {uploadStatus === 'error' && (
            <p role="alert" className="error">
              {uploadError}
            </p>
          )}
        </div>

        <p className="hint">Select documents to scope retrieval (optional).</p>
        {storedError && (
          <p role="alert" className="error">
            {storedError}
          </p>
        )}
        {stored.length === 0 && !storedError && (
          <p className="hint">No documents yet — upload a PDF to begin.</p>
        )}
        <ul className="document-list">
          {stored.map((doc) => (
            <li key={doc.id}>
              <label className="document-item">
                <input
                  type="checkbox"
                  checked={selectedIds.includes(doc.id)}
                  onChange={() => toggle(doc.id)}
                />
                <span className="document-meta">
                  <span className="document-title">{doc.title}</span>
                  <span className="document-sub">
                    {doc.pageCount} pages · {doc.chunkCount} chunks
                  </span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel chat" aria-labelledby="retrieval-heading">
        <h2 id="retrieval-heading">Retrieved evidence</h2>
        <p className="evidence-disclaimer">
          These are <strong>source passages retrieved from your documents</strong> —
          verbatim excerpts with page citations. They are <strong>not</strong> an
          AI-generated answer or conclusion.
        </p>

        <form className="composer" onSubmit={submitQuery}>
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
          <p role="alert" className="error">
            {retrievalError}
          </p>
        )}

        {response && (
          <div className="passages" aria-live="polite">
            <p className="hint">
              {response.passages.length} passage(s) · embedding model{' '}
              <code>{response.embeddingModel}</code>
            </p>
            {response.passages.length === 0 && (
              <p className="hint">No matching evidence found in the selected documents.</p>
            )}
            {response.passages.map((p) => (
              <article key={p.chunkId} className="passage">
                <header className="passage-head">
                  <button
                    type="button"
                    className="citation-link"
                    title={`${p.documentTitle} — page ${p.page}, characters ${p.charStart}–${p.charEnd}`}
                  >
                    {p.citation}
                  </button>
                  <span className="passage-scores">
                    lex {p.scores.lexical.toFixed(3)} · sem {p.scores.semantic.toFixed(3)} ·
                    fused {p.scores.fused.toFixed(4)}
                  </span>
                </header>
                <blockquote className="passage-text">{p.text}</blockquote>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
