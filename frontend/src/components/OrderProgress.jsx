const STAGES = [
  ['ordered', 'Ordered'],
  ['shipped', 'Shipped'],
  ['at_port', 'At port'],
  ['clearing', 'Clearing'],
  ['delivered', 'Delivered'],
]

function OrderProgress({ currentStage }) {
  const reached = STAGES.findIndex(([key]) => key === currentStage)

  return (
    <ol className="flex flex-wrap gap-x-2 gap-y-3">
      {STAGES.map(([key, label], index) => {
        const done = index <= reached
        return (
          <li key={key} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className={`h-2 w-2 rounded-full ${done ? 'bg-ink' : 'bg-line'}`}
            />
            <span
              className={`text-badge uppercase ${done ? 'text-ink' : 'text-ink-mute'}`}
            >
              {label}
            </span>
            {index < STAGES.length - 1 && (
              <span aria-hidden="true" className="ml-1 h-px w-6 bg-line" />
            )}
          </li>
        )
      })}
    </ol>
  )
}

export default OrderProgress
