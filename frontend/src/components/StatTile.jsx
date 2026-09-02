import {
  sparklineArea,
  sparklineEnd,
  sparklinePoints,
} from '../lib/chartScale'

/** One headline number.
 *
 *  A single current value is a stat tile, not a one-bar chart - there is
 *  nothing to compare it against inside its own frame, so the frame is wasted.
 *  The trend goes beside it as a sparkline, which is the smallest thing that
 *  answers "and is that going up".
 */

const SPARK_WIDTH = 120
const SPARK_HEIGHT = 28

/** Past this, a percentage stops informing anybody.
 *
 *  Real figure from the dev database: KES 5,000 one month and 8.9M the next is
 *  "up 177,900%", which is arithmetic nobody can use. Growth against a month
 *  that barely traded is a fact about the small month, so say that instead. */
const ABSURD = 999

function Delta({ percent, from }) {
  // Null is not zero. No trade last month means the comparison cannot be
  // made, and printing an infinity or a cheerful 100% would both be lies.
  if (percent === null || percent === undefined) {
    return <span className="text-meta text-ink-mute">no month before it</span>
  }

  if (Math.abs(percent) > ABSURD && from !== undefined) {
    return <span className="text-meta text-ink-soft">up from {from}</span>
  }

  const up = percent >= 0
  return (
    <span className="text-meta text-ink-soft">
      <span aria-hidden="true">{up ? '▲' : '▼'}</span>{' '}
      {up ? 'up' : 'down'} {Math.abs(percent)}% on last month
    </span>
  )
}

function StatTile({ label, value, note, delta, deltaFrom, trend, tone = 'plain' }) {
  const end =
    trend && trend.length > 1
      ? sparklineEnd(trend, SPARK_WIDTH, SPARK_HEIGHT)
      : null

  return (
    <div className="border border-line bg-surface p-6">
      <p className="text-badge uppercase text-ink-soft">{label}</p>

      <p
        className={`mt-3 font-serif text-section ${
          tone === 'quiet' ? 'text-ink-soft' : 'text-ink'
        }`}
      >
        {value}
      </p>

      {delta !== undefined && (
        <p className="mt-2">
          <Delta percent={delta} from={deltaFrom} />
        </p>
      )}

      {note && <p className="mt-2 text-meta text-ink-soft">{note}</p>}

      {trend && trend.length > 1 && (
        <svg
          viewBox={`0 0 ${SPARK_WIDTH} ${SPARK_HEIGHT}`}
          className="mt-4 w-full"
          aria-hidden="true"
        >
          {/* Solid, never a gradient (§2.2). The fill is what gives a trend a
              shape at the size a tile has room for; a bare 2px line at this
              scale reads as an afterthought. */}
          <path
            d={sparklineArea(trend, SPARK_WIDTH, SPARK_HEIGHT)}
            fill="var(--color-line)"
          />
          <polyline
            points={sparklinePoints(trend, SPARK_WIDTH, SPARK_HEIGHT)}
            fill="none"
            stroke="var(--color-ink-mute)"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          {/* Where it got to. Without it the eye has to find the right-hand
              end of a line that may be flat. */}
          {end && <circle cx={end.x} cy={end.y} r="2.5" fill="var(--color-ink)" />}
        </svg>
      )}
    </div>
  )
}

export default StatTile
