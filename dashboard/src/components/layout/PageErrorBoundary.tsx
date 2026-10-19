import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

type Props = { children: ReactNode }
type State = { hasError: boolean }

/** Page-level recovery boundary; never displays stack traces or account data. */
export default class PageErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // No details printed in production. Diagnostics belong in approved telemetry,
    // not screen output where internal identifiers could be exposed.
    if (import.meta.env.DEV) {
      console.error('Dashboard view failed', error, info.componentStack)
    }
  }

  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <section role="alert" className="mx-auto flex max-w-xl flex-col items-start gap-4 px-6 py-16">
        <div className="rounded-lg border border-border bg-card p-3 text-muted-foreground">
          <AlertTriangle className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-foreground">This view couldn't load</h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Your account and trading engine are unaffected by this screen error.
            You can retry the view or choose another section.
          </p>
        </div>
        <button
          type="button"
          onClick={() => this.setState({ hasError: false })}
          className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" /> Retry view
        </button>
      </section>
    )
  }
}
