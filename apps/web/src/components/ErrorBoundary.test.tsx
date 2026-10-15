import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ErrorBoundary } from './ErrorBoundary';

function Boom(): never {
  throw new Error('kaboom');
}

describe('ErrorBoundary', () => {
  // React logs caught errors to console.error; silence it for clean output.
  beforeEach(() => vi.spyOn(console, 'error').mockImplementation(() => {}));
  afterEach(() => vi.restoreAllMocks());

  it('renders children when nothing throws', () => {
    render(
      <ErrorBoundary>
        <p>all good</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText('all good')).toBeInTheDocument();
  });

  it('catches a render error and shows a recoverable fallback', async () => {
    const user = userEvent.setup();
    function Flaky({ crash }: { crash: boolean }) {
      return crash ? <Boom /> : <p>recovered</p>;
    }
    const { rerender } = render(
      <ErrorBoundary>
        <Flaky crash />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong.');
    expect(screen.getByText('kaboom')).toBeInTheDocument();

    // "Try again" clears the error; re-rendering healthy children recovers.
    rerender(
      <ErrorBoundary>
        <Flaky crash={false} />
      </ErrorBoundary>,
    );
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(screen.getByText('recovered')).toBeInTheDocument();
  });
});
