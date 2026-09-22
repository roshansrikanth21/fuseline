import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

type State = { error: Error | null }

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Fuseline UI error:', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <section className="panel" role="alert">
        <h1>Something went wrong</h1>
        <p className="muted">
          The interface hit an unexpected error. Your case data is safe on disk; reloading usually recovers.
        </p>
        <pre className="code-block">{this.state.error.message}</pre>
        <div className="row">
          <button type="button" className="btn" onClick={() => window.location.reload()}>
            Reload
          </button>
          <button type="button" className="btn secondary" onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </div>
      </section>
    )
  }
}
