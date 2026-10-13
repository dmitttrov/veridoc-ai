import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type {
  ChatStreamEvent,
  DocumentSummary,
  RetrievalResponse,
  StoredDocument,
} from '@veridoc/contracts';
import { App } from './App';

const documents: DocumentSummary[] = [
  {
    id: 'doc-acme-fy2023',
    title: 'Acme Robotics — Annual Report FY2023 (sample)',
    issuer: 'Acme Robotics (fictional)',
    period: 'FY2023',
    pageCount: 84,
  },
];

const stored: StoredDocument[] = [
  {
    id: '11111111-1111-1111-1111-111111111111',
    title: 'acme robotics fy2023',
    filename: 'acme_robotics_fy2023.pdf',
    pageCount: 6,
    chunkCount: 6,
    sizeBytes: 2048,
  },
];

const retrievalResponse: RetrievalResponse = {
  query: 'revenue',
  embeddingModel: 'veridoc-deterministic-emb-v1',
  embeddingDim: 384,
  passages: [
    {
      chunkId: '22222222-2222-2222-2222-222222222222',
      documentId: stored[0]!.id,
      documentTitle: 'acme robotics fy2023',
      page: 2,
      text: 'Total revenue for fiscal year 2023 was 482.6 million dollars.',
      charStart: 0,
      charEnd: 60,
      scores: { lexical: 0.12, semantic: 0.84, fused: 0.0325 },
      citation: 'acme robotics fy2023, p.2',
    },
  ],
};

const streamEvents: ChatStreamEvent[] = [
  { type: 'token', text: 'Hello ' },
  { type: 'token', text: 'world.' },
  { type: 'done', mock: true, model: 'veridoc-mock-0.1', tokenCount: 2 },
];

vi.mock('./lib/api', () => ({
  fetchDocuments: vi.fn(async () => documents),
  fetchStoredDocuments: vi.fn(async () => stored),
  uploadDocument: vi.fn(),
  retrieve: vi.fn(async () => retrievalResponse),
  // eslint-disable-next-line require-yield
  streamChat: vi.fn(async function* () {
    for (const event of streamEvents) yield event;
  }),
}));

afterEach(() => {
  vi.clearAllMocks();
});

describe('App — retrieval view (default)', () => {
  it('distinguishes retrieved evidence from generated answers', async () => {
    render(<App />);
    expect(
      screen.getByText(/an AI-generated answer or conclusion/i),
    ).toBeInTheDocument();
    expect(
      await screen.findByText('acme robotics fy2023'),
    ).toBeInTheDocument();
  });

  it('retrieves and renders source passages with citations', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('acme robotics fy2023');

    await user.type(screen.getByLabelText('Question'), 'What was revenue?');
    await user.click(screen.getByRole('button', { name: 'Find evidence' }));

    expect(
      await screen.findByText(/Total revenue for fiscal year 2023/),
    ).toBeInTheDocument();
    expect(screen.getByText('acme robotics fy2023, p.2')).toBeInTheDocument();
  });
});

describe('App — mock chat view', () => {
  it('streams a mock answer and shows the MOCK MODE badge', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('tab', { name: 'Mock Chat' }));
    expect(screen.getByText('MOCK MODE')).toBeInTheDocument();

    await user.type(screen.getByLabelText('Your question'), 'What was revenue?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('What was revenue?')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Hello world.')).toBeInTheDocument());
  });
});
