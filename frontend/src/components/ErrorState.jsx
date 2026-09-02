import Button from './Button'
function ErrorState({ title = 'Something went wrong', message, onRetry }) {
  return (
    <div className="border border-line bg-surface p-12 text-center">
      <p className="font-serif text-section">{title}</p>
      {message && <p className="mt-3 text-model text-ink-soft">{message}</p>}
      {/* No retry button when retrying cannot help - a deleted car stays deleted. */}
      {onRetry && (
        <Button
          variant="secondary"
          size="large"
          className="mt-8"
          onClick={onRetry}
        >
          Try again
        </Button>
      )}
    </div>
  )
}

export default ErrorState
