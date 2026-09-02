import { formatPrice } from '../lib/format'

/** How the money actually arrives, as one part-to-whole bar.
 *
 *  A horizontal bar rather than twelve stacked columns: the question is not
 *  "how did February differ from March", it is "what share of the business
 *  only closes by bank transfer" - and that answer is one number per method.
 *  It is also the only shape where all three can be labelled directly, which
 *  matters more here than anywhere else on the screen, because the lightest
 *  ink step does not carry enough contrast to identify a segment on its own.
 *
 *  Why it is worth a panel at all: Paystack refuses large amounts outright and
 *  M-PESA stops at 250,000, so a high-value car can only be collected by bank
 *  transfer. The manual share is the share of trade the automated rails cannot
 *  touch, and it is invisible everywhere else in the dashboard.
 */

const METHODS = [
  ['card', 'Card', 'var(--color-ink)'],
  ['mpesa', 'M-PESA', 'var(--color-ink-soft)'],
  ['manual', 'Bank transfer', 'var(--color-ink-mute)'],
]

const GAP = 0.4 // percent of the track, so the fills never touch

function MethodShare({ months = [] }) {
  const totals = METHODS.map(([key, label, fill]) => ({
    key,
    label,
    fill,
    amount: months.reduce((sum, month) => sum + (Number(month[key]) || 0), 0),
  }))

  const grand = totals.reduce((sum, entry) => sum + entry.amount, 0)

  if (grand <= 0) {
    return (
      <p className="text-meta text-ink-soft">
        Nothing has been collected in this window, so there is no split to show.
      </p>
    )
  }

  const withShare = totals.map((entry) => ({
    ...entry,
    percent: (entry.amount / grand) * 100,
  }))

  return (
    <div>
      <div className="flex h-10 w-full overflow-hidden border border-line">
        {withShare.map((entry, index) =>
          entry.percent > 0 ? (
            <div
              key={entry.key}
              className="h-full"
              style={{
                background: entry.fill,
                width: `calc(${entry.percent}% - ${index > 0 ? GAP : 0}%)`,
                marginLeft: index > 0 ? `${GAP}%` : 0,
              }}
              title={`${entry.label}: ${formatPrice(entry.amount)}`}
            />
          ) : null,
        )}
      </div>

      {/* Direct labels, not a colour key: identity never rests on the shade. */}
      <dl className="mt-6 space-y-3">
        {withShare.map((entry) => (
          <div key={entry.key} className="flex items-baseline gap-3">
            <span
              aria-hidden="true"
              className="h-2 w-2 shrink-0 self-center border border-line"
              style={{ background: entry.fill }}
            />
            <dt className="text-meta">{entry.label}</dt>
            <span aria-hidden="true" className="mx-1 flex-1 border-b border-line" />
            <dd className="text-meta text-ink-soft">
              {formatPrice(entry.amount)}{' '}
              <span className="text-ink">({Math.round(entry.percent)}%)</span>
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

export default MethodShare
