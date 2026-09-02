import { Component } from 'react'
import Button from './Button'

/** Catches render-time crashes anywhere below it. This has to be a class -
 *  getDerivedStateFromError and componentDidCatch have no hook equivalent.
 *  Without it, a thrown error unmounts the whole tree and leaves a blank page
 *  with the reason buried in the console. */
class ErrorBoundary extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    console.error('Unhandled render error', error, info)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="flex min-h-screen items-center justify-center bg-page p-5 text-ink">
        <div className="max-w-[440px] border border-line bg-surface p-12 text-center">
          <p className="font-serif text-section">Something broke</p>
          <p className="mt-3 text-model text-ink-soft">
            This page hit an unexpected error. Reloading usually fixes it.
          </p>
          <Button
            variant="secondary"
            size="large"
            className="mt-8"
            onClick={() => window.location.reload()}
          >
            Reload
          </Button>
        </div>
      </div>
    )
  }
}

export default ErrorBoundary
