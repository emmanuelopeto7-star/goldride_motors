function ErrorState({ title = 'Something went wrong', message, onRetry }) {
  return (
    <div className="border border-line bg-surface p-12 text-center">
      <p className="font-serif text-section">{title}</p>
      {message && <p className="mt-3 text-model text-ink-soft">{message}</p>}
      {/* No retry button when retrying cannot help - a deleted car stays deleted. */}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-8 h-12 border border-ink px-8 text-badge uppercase"
        >
          Try again
        </button>
      )}
    </div>
  )
}

export default ErrorState
