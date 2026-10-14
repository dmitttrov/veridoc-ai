import type { DocumentSummary } from '@veridoc/contracts';
import styles from '../styles.module.css';

interface Props {
  documents: DocumentSummary[];
  selectedIds: string[];
  loading: boolean;
  error: string | null;
  onToggle: (id: string) => void;
}

export function DocumentList({
  documents,
  selectedIds,
  loading,
  error,
  onToggle,
}: Props) {
  return (
    <section className={styles.panel} aria-labelledby="documents-heading">
      <h2 id="documents-heading">Documents</h2>
      <p className={styles.hint}>Select documents to ground your question (optional).</p>

      {loading && <p role="status">Loading documents…</p>}
      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}

      {!loading && !error && (
        <ul className={styles['document-list']}>
          {documents.map((doc) => {
            const checked = selectedIds.includes(doc.id);
            return (
              <li key={doc.id}>
                <label className={styles['document-item']}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggle(doc.id)}
                  />
                  <span className={styles['document-meta']}>
                    <span className={styles['document-title']}>{doc.title}</span>
                    <span className={styles['document-sub']}>
                      {doc.issuer} · {doc.period} · {doc.pageCount} pages
                    </span>
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
