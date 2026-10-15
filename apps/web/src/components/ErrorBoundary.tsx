import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** Optional custom fallback; defaults to a minimal recoverable panel. */
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Top-level error boundary. A render-time throw anywhere in the tree is caught
 * here and shown as a recoverable panel instead of a blank white page.
 *
 * Only class components can be error boundaries (no hook equivalent exists for
 * `componentDidCatch`), so this stays a class on purpose.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surface for diagnostics; a real deployment would forward this to a
    // reporting service. Never logs user document content (there is none here).
    console.error('Unhandled UI error:', error, info.componentStack);
  }

  private reset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback;
      // Inline styles on purpose: the boundary must render even if the app's
      // stylesheet is itself implicated in the failure.
      return (
        <div
          role="alert"
          style={{
            margin: '2rem',
            padding: '1rem',
            borderRadius: 10,
            background: '#450a0a',
            color: '#f87171',
            border: '1px solid #f87171',
          }}
        >
          <strong>Something went wrong.</strong>
          <p>{this.state.error.message}</p>
          <button type="button" onClick={this.reset}>
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
