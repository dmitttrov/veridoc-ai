import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ChatStreamEvent, DocumentSummary } from '@veridoc/contracts';
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

const streamEvents: ChatStreamEvent[] = [
  { type: 'token', text: 'Hello ' },
  { type: 'token', text: 'world.' },
  {
    type: 'citations',
    citations: [
      {
        documentId: 'doc-acme-fy2023',
        documentTitle: 'Acme Robotics — Annual Report FY2023 (sample)',
        page: 12,
        snippet: 'illustrative figures only',
      },
    ],
  },
  { type: 'done', mock: true, model: 'veridoc-mock-0.1', tokenCount: 2 },
];

vi.mock('./lib/api', () => ({
  fetchDocuments: vi.fn(async () => documents),
  // eslint-disable-next-line require-yield
  streamChat: vi.fn(async function* () {
    for (const event of streamEvents) yield event;
  }),
}));

afterEach(() => {
  vi.clearAllMocks();
});

describe('App', () => {
  it('renders the document list and the mock-mode badge', async () => {
    render(<App />);
    expect(screen.getByText('MOCK MODE')).toBeInTheDocument();
    expect(
      await screen.findByText('Acme Robotics — Annual Report FY2023 (sample)'),
    ).toBeInTheDocument();
  });

  it('streams an answer with citations in response to a question', async () => {
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText('Acme Robotics — Annual Report FY2023 (sample)');

    const input = screen.getByLabelText('Your question');
    await user.type(input, 'What was revenue?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    // The user's message and the streamed assistant answer both appear.
    expect(await screen.findByText('What was revenue?')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Hello world.')).toBeInTheDocument());

    // The grounded citation is rendered.
    expect(await screen.findByText(/p\.12/)).toBeInTheDocument();
  });
});
