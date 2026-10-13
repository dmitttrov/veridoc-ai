import { useCallback, useEffect, useState } from 'react';
import type {
  DocumentIngestionResult,
  RetrievalResponse,
  StoredDocument,
} from '@veridoc/contracts';
import {
  fetchStoredDocuments,
  retrieve,
  uploadDocument,
} from '../lib/api';

export type UploadStatus = 'idle' | 'uploading' | 'done' | 'error';
export type RetrievalStatus = 'idle' | 'loading' | 'done' | 'error';

export interface UseRetrieval {
  stored: StoredDocument[];
  storedError: string | null;
  selectedIds: string[];
  toggle: (id: string) => void;

  uploadStatus: UploadStatus;
  uploadResult: DocumentIngestionResult | null;
  uploadError: string | null;
  upload: (file: File) => Promise<void>;

  retrievalStatus: RetrievalStatus;
  response: RetrievalResponse | null;
  retrievalError: string | null;
  runRetrieval: (query: string) => Promise<void>;
}

export function useRetrieval(): UseRetrieval {
  const [stored, setStored] = useState<StoredDocument[]>([]);
  const [storedError, setStoredError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [uploadResult, setUploadResult] = useState<DocumentIngestionResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [retrievalStatus, setRetrievalStatus] = useState<RetrievalStatus>('idle');
  const [response, setResponse] = useState<RetrievalResponse | null>(null);
  const [retrievalError, setRetrievalError] = useState<string | null>(null);

  const refreshStored = useCallback(async (signal?: AbortSignal) => {
    try {
      const docs = await fetchStoredDocuments(signal);
      setStored(docs);
      setStoredError(null);
    } catch (err) {
      if (signal?.aborted) return;
      setStoredError(err instanceof Error ? err.message : 'Failed to load documents');
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refreshStored(controller.signal);
    return () => controller.abort();
  }, [refreshStored]);

  const toggle = useCallback((id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }, []);

  const upload = useCallback(
    async (file: File) => {
      setUploadStatus('uploading');
      setUploadError(null);
      setUploadResult(null);
      try {
        const result = await uploadDocument(file);
        setUploadResult(result);
        setUploadStatus('done');
        await refreshStored();
        // Auto-select the freshly ingested document for convenience.
        setSelectedIds((prev) =>
          prev.includes(result.documentId) ? prev : [...prev, result.documentId],
        );
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : 'Upload failed');
        setUploadStatus('error');
      }
    },
    [refreshStored],
  );

  const runRetrieval = useCallback(
    async (query: string) => {
      const trimmed = query.trim();
      if (!trimmed) return;
      setRetrievalStatus('loading');
      setRetrievalError(null);
      try {
        const res = await retrieve({ query: trimmed, documentIds: selectedIds, topK: 5 });
        setResponse(res);
        setRetrievalStatus('done');
      } catch (err) {
        setRetrievalError(err instanceof Error ? err.message : 'Retrieval failed');
        setRetrievalStatus('error');
      }
    },
    [selectedIds],
  );

  return {
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
  };
}
