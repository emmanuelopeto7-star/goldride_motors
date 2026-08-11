function EmptyState({ title, message, action }) {
  return (
    <div className="border border-line bg-surface p-12 text-center">
      <p className="font-serif text-section">{title}</p>
      {message && <p className="mt-3 text-model text-ink-soft">{message}</p>}
      {action}
    </div>
  )
}

export default EmptyState
