import { useRef } from 'react';
import type { DocumentIngestionResult, StoredDocument } from '@veridoc/contracts';
import type { UploadStatus } from '../hooks/useRetrieval';
import styles from '../styles.module.css';

interface Props {
  stored: StoredDocument[];
  storedError: string | null;
  selectedIds: string[];
  onToggle: (id: string) => void;
  uploadStatus: UploadStatus;
  uploadResult: DocumentIngestionResult | null;
  uploadError: string | null;
  onUpload: (file: File) => void;
  hint: string;
}

export function DocumentsPanel({
  stored,
  storedError,
  selectedIds,
  onToggle,
  uploadStatus,
  uploadResult,
  uploadError,
  onUpload,
  hint,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const file = e.target.files?.[0];
    if (file) onUpload(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <section className={styles.panel} aria-labelledby="documents-heading">
      <h2 id="documents-heading">Documents</h2>

      <div className={styles.upload}>
        <label className={styles['upload-label']}>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={onFileChange}
            disabled={uploadStatus === 'uploading'}
          />
        </label>
        {uploadStatus === 'uploading' && (
          <p role="status" className={styles.hint}>
            Ingesting… parsing, chunking, and embedding.
          </p>
        )}
        {uploadStatus === 'done' && uploadResult && (
          <p role="status" className={styles['ingest-ok']}>
            {uploadResult.alreadyIngested
              ? `Already ingested (${uploadResult.pageCount} pages, ${uploadResult.chunkCount} chunks).`
              : `Ingested: ${uploadResult.pageCount} pages, ${uploadResult.chunkCount} chunks.`}
          </p>
        )}
        {uploadStatus === 'error' && (
          <p role="alert" className={styles.error}>
            {uploadError}
          </p>
        )}
      </div>

      <p className={styles.hint}>{hint}</p>
      {storedError && (
        <p role="alert" className={styles.error}>
          {storedError}
        </p>
      )}
      {stored.length === 0 && !storedError && (
        <p className={styles.hint}>No documents yet — upload a PDF to begin.</p>
      )}
      <ul className={styles['document-list']}>
        {stored.map((doc) => (
          <li key={doc.id}>
            <label className={styles['document-item']}>
              <input
                type="checkbox"
                checked={selectedIds.includes(doc.id)}
                onChange={() => onToggle(doc.id)}
              />
              <span className={styles['document-meta']}>
                <span className={styles['document-title']}>{doc.title}</span>
                <span className={styles['document-sub']}>
                  {doc.pageCount} pages · {doc.chunkCount} chunks
                </span>
              </span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}
