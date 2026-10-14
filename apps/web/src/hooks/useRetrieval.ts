import { useCallback, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type {
  DocumentIngestionResult,
  RetrievalResponse,
  StoredDocument,
} from '@veridoc/contracts';
import { fetchStoredDocuments, retrieve, uploadDocument } from '../lib/api';

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
  upload: (file: File) => void;

  retrievalStatus: RetrievalStatus;
  response: RetrievalResponse | null;
  retrievalError: string | null;
  runRetrieval: (query: string) => void;
}

const STORED_DOCUMENTS_KEY = ['stored-documents'] as const;

const errMessage = (err: unknown, fallback: string): string =>
  err instanceof Error ? err.message : fallback;

export function useRetrieval(): UseRetrieval {
  const queryClient = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const storedQuery = useQuery({
    queryKey: STORED_DOCUMENTS_KEY,
    queryFn: ({ signal }) => fetchStoredDocuments(signal),
  });

  const toggle = useCallback((id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }, []);

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadDocument(file),
    onSuccess: (result) => {
      // Freshly ingested document should appear in the list and be preselected.
      void queryClient.invalidateQueries({ queryKey: STORED_DOCUMENTS_KEY });
      setSelectedIds((prev) =>
        prev.includes(result.documentId) ? prev : [...prev, result.documentId],
      );
    },
  });

  const retrievalMutation = useMutation({
    mutationFn: (query: string) => retrieve({ query, documentIds: selectedIds, topK: 5 }),
  });

  const upload = useCallback(
    (file: File) => uploadMutation.mutate(file),
    [uploadMutation],
  );

  const runRetrieval = useCallback(
    (query: string) => {
      const trimmed = query.trim();
      if (!trimmed) return;
      retrievalMutation.mutate(trimmed);
    },
    [retrievalMutation],
  );

  const uploadStatus: UploadStatus =
    uploadMutation.status === 'pending'
      ? 'uploading'
      : uploadMutation.status === 'success'
        ? 'done'
        : uploadMutation.status === 'error'
          ? 'error'
          : 'idle';

  const retrievalStatus: RetrievalStatus =
    retrievalMutation.status === 'pending'
      ? 'loading'
      : retrievalMutation.status === 'success'
        ? 'done'
        : retrievalMutation.status === 'error'
          ? 'error'
          : 'idle';

  return {
    stored: storedQuery.data ?? [],
    storedError: storedQuery.isError
      ? errMessage(storedQuery.error, 'Failed to load documents')
      : null,
    selectedIds,
    toggle,
    uploadStatus,
    uploadResult: uploadMutation.data ?? null,
    uploadError: uploadMutation.isError
      ? errMessage(uploadMutation.error, 'Upload failed')
      : null,
    upload,
    retrievalStatus,
    response: retrievalMutation.data ?? null,
    retrievalError: retrievalMutation.isError
      ? errMessage(retrievalMutation.error, 'Retrieval failed')
      : null,
    runRetrieval,
  };
}
