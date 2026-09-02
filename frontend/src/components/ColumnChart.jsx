import { useId, useState } from 'react'
import { compactPrice, formatPrice } from '../lib/format'
import {
  columnPath,
  labelledColumns,
  layoutColumns,
  trailingAverage,
  yearBoundaries,
} from '../lib/chartScale'

/** A stacked column chart, drawn by hand.
 *
 *  Hand-rolled rather than a charting library on purpose. Twelve columns is
 *  eighty lines of SVG, while a library arrives with rounded corners, tinted
 *  gradients, shadowed tooltips and a colour cycle - every one of which
 *  contradicts the design rules (§2 no colour, §3.1 radius 0, §3.2 shadows
 *  only on dropdowns), so the work would be spent suppressing it.
 *
 *  Four marks, not one, because bare columns leave real questions unanswered:
 *  a **trailing average**, because one 8.9M car otherwise becomes the shape of
 *  the whole year; a **year divider**, because a twelve-month window nearly
 *  always crosses one and "Jan" between "Dec" and "Feb" reads as the same
 *  year; a **dashed outline on the current month**, because it is three weeks
 *  of trade standing against twelve finished months and unmarked it reads as a
 *  collapse; and a **legend**, for the reason below.
 *
 *  Colour: the palette is the ink ramp, because the brand has no hues to
 *  spend. Read as a sequential ramp it is sound - the adjacent steps separate
 *  by well over the threshold under both deutan and tritan simulation. The one
 *  thing that ramp cannot do is carry identity on its own: `--color-ink-mute`
 *  sits at 2.74:1 against the surface, under the 3:1 floor, so any chart with
 *  more than one series ships a legend and a table view and never asks anyone
 *  to tell the series apart by shade alone. DESIGN.md §11.
 *
 *  The geometry is in lib/chartScale.js, under test. This file only draws.
 */

const VIEW_WIDTH = 1000
const VIEW_HEIGHT = 300
const PAD_TOP = 32
const PAD_BOTTOM = 32
/** The axis figures live here, clear of the first column. */
const PAD_LEFT = 48

/** Months behind the trailing mean. Three is a quarter, which is the shortest
 *  window that survives one large sale landing in one month. */
const AVERAGE_WINDOW = 3

const SHADES = {
  ink: 'var(--color-ink)',
  soft: 'var(--color-ink-soft)',
  mute: 'var(--color-ink-mute)',
}

function ColumnChart({
  data = [],
  series = [{ key: 'total', label: 'Collected', shade: 'ink' }],
  caption,
  /** The last column is the month we are standing in, and is still filling. */
  lastIsPartial = true,
}) {
  const [active, setActive] = useState(null)
  const titleId = useId()

  const keys = series.map((entry) => entry.key)
  const shadeFor = Object.fromEntries(
    series.map((entry) => [entry.key, SHADES[entry.shade] ?? SHADES.ink]),
  )
  const labelFor = Object.fromEntries(
    series.map((entry) => [entry.key, entry.label]),
  )

  const { columns, ticks, baseline, plotLeft, yFor } = layoutColumns({
    data,
    keys,
    width: VIEW_WIDTH,
    height: VIEW_HEIGHT,
    padTop: PAD_TOP,
    padBottom: PAD_BOTTOM,
    padLeft: PAD_LEFT,
  })

  const labelled = labelledColumns(columns)
  const boundaries = yearBoundaries(columns)
  const averages = trailingAverage(
    columns.map((column) => column.total),
    AVERAGE_WINDOW,
  )
  const averageLine = columns
    .map((column, index) =>
      averages[index] === null
        ? null
        : `${column.centreX},${yFor(averages[index])}`,
    )
    .filter(Boolean)
    .join(' ')

  const partialIndex =
    lastIsPartial && columns.length > 0 ? columns.length - 1 : -1
  const hovered = active === null ? null : columns[active]

  // A tooltip centred on the last column hangs off the side of the panel.
  // Near either edge it hangs off the column instead.
  const hoveredAt = hovered ? (hovered.centreX / VIEW_WIDTH) * 100 : 0
  const anchor =
    hoveredAt > 85 ? '-translate-x-full' : hoveredAt < 15 ? '' : '-translate-x-1/2'

  return (
    <div>
      <div className="relative">
        <svg
          viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
          className="w-full"
          role="img"
          aria-labelledby={titleId}
          onMouseLeave={() => setActive(null)}
        >
          <title id={titleId}>{caption}</title>

          {/* Recessive: hairlines in the border token, never in ink. A grid
              that competes with the bars is a grid the reader looks past. */}
          {ticks.map((tick) => (
            <g key={tick.value}>
              <line
                x1={plotLeft}
                x2={VIEW_WIDTH}
                y1={tick.y}
                y2={tick.y}
                stroke="var(--color-line)"
                strokeWidth="1"
              />
              <text
                x={plotLeft - 10}
                y={tick.y + 4}
                textAnchor="end"
                className="fill-ink-mute"
                fontSize="11"
              >
                {compactPrice(tick.value)}
              </text>
            </g>
          ))}

          {boundaries.map((boundary) => (
            <g key={boundary.year}>
              <line
                x1={boundary.x}
                x2={boundary.x}
                y1={PAD_TOP - 14}
                y2={baseline}
                stroke="var(--color-line-hover)"
                strokeWidth="1"
              />
              <text
                x={boundary.x + 6}
                y={PAD_TOP - 18}
                className="fill-ink-mute"
                fontSize="10"
                letterSpacing="0.08em"
              >
                {boundary.year}
              </text>
            </g>
          ))}

          {hovered && (
            <line
              x1={hovered.centreX}
              x2={hovered.centreX}
              y1={PAD_TOP - 14}
              y2={baseline}
              stroke="var(--color-line-hover)"
              strokeWidth="1"
            />
          )}

          <g className="chart-rise">
            {columns.map((column) => (
              <g key={column.month ?? column.label}>
                {column.segments.map((segment) =>
                  segment.height > 0 ? (
                    <path
                      key={segment.key}
                      d={
                        segment.rounded
                          ? columnPath(
                              segment.x,
                              segment.y,
                              segment.width,
                              segment.height,
                            )
                          : `M ${segment.x} ${segment.y} h ${segment.width} v ${segment.height} h -${segment.width} Z`
                      }
                      fill={shadeFor[segment.key]}
                      opacity={
                        active === null || active === column.index ? 1 : 0.45
                      }
                    />
                  ) : null,
                )}

                {/* The month in progress. Outlined to its own height, never to
                    a guess at where it will end - the shortfall is the point. */}
                {column.index === partialIndex && (
                  <rect
                    x={column.x}
                    y={column.top - 6}
                    width={column.width}
                    height={baseline - column.top + 6}
                    fill="none"
                    stroke="var(--color-ink-mute)"
                    strokeWidth="1"
                    strokeDasharray="3 3"
                  />
                )}
              </g>
            ))}
          </g>

          {/* Over the columns, because it is the answer they are too noisy to
              give. 2px, so it reads as a mark rather than a gridline. */}
          {averageLine && (
            <polyline
              points={averageLine}
              fill="none"
              stroke="var(--color-ink-soft)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {columns.map((column) => (
            <g key={`labels-${column.month ?? column.label}`}>
              {labelled.has(column.index) && (
                <text
                  x={column.centreX}
                  y={column.top - (column.index === partialIndex ? 14 : 8)}
                  textAnchor="middle"
                  className="fill-ink-soft"
                  fontSize="11"
                >
                  {compactPrice(column.total)}
                </text>
              )}

              <text
                x={column.centreX}
                y={baseline + 18}
                textAnchor="middle"
                className={
                  column.index === columns.length - 1
                    ? 'fill-ink'
                    : 'fill-ink-mute'
                }
                fontSize="11"
              >
                {column.label}
              </text>

              {column.index === partialIndex && (
                <text
                  x={column.centreX}
                  y={baseline + 29}
                  textAnchor="middle"
                  className="fill-ink-mute"
                  fontSize="9"
                  letterSpacing="0.08em"
                >
                  SO FAR
                </text>
              )}

              {/* The hit target is the whole band, not the bar: an empty month
                  still has to be hoverable, and a 3px column is not a target
                  anybody can hit. */}
              <rect
                x={column.bandX}
                y="0"
                width={column.bandWidth}
                height={VIEW_HEIGHT}
                fill="transparent"
                tabIndex={0}
                role="button"
                aria-label={`${column.label} ${column.year ?? ''}: ${formatPrice(column.total)}`}
                onMouseEnter={() => setActive(column.index)}
                onFocus={() => setActive(column.index)}
                onBlur={() => setActive(null)}
              />
            </g>
          ))}
        </svg>

        {hovered && (
          <div
            className={`pointer-events-none absolute top-0 z-10 min-w-[200px] border border-line bg-surface px-4 py-3 ${anchor}`}
            style={{ left: `${hoveredAt}%` }}
          >
            <p className="text-badge uppercase text-ink-mute">
              {hovered.label} {hovered.year}
              {hovered.index === partialIndex && ' · so far'}
            </p>
            <p className="mt-1 text-model">{formatPrice(hovered.total)}</p>
            {series.length > 1 && (
              <dl className="mt-2 space-y-1">
                {series.map((entry) => (
                  <div key={entry.key} className="flex items-center gap-3">
                    <span
                      aria-hidden="true"
                      className="h-2 w-2 shrink-0"
                      style={{ background: shadeFor[entry.key] }}
                    />
                    <dt className="text-meta text-ink-soft">
                      {labelFor[entry.key]}
                    </dt>
                    <dd className="ml-auto text-meta">
                      {formatPrice(hovered[entry.key])}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
            {averages[hovered.index] !== null && (
              <p className="mt-2 border-t border-line pt-2 text-meta text-ink-soft">
                {AVERAGE_WINDOW}-month average{' '}
                {formatPrice(averages[hovered.index])}
              </p>
            )}
            {Number(hovered.refunded) > 0 && (
              <p className="mt-2 text-meta text-ink-soft">
                {formatPrice(hovered.refunded)} refunded
              </p>
            )}
          </div>
        )}
      </div>

      {/* Always present for more than one series, and never the only way to
          tell them apart - the table under the chart carries the figures. */}
      {(series.length > 1 || averageLine) && (
        <ul className="mt-6 flex flex-wrap items-center gap-x-8 gap-y-3">
          {series.length > 1 &&
            series.map((entry) => (
              <li key={entry.key} className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="h-2 w-2 border border-line"
                  style={{ background: shadeFor[entry.key] }}
                />
                <span className="text-meta text-ink-soft">{entry.label}</span>
              </li>
            ))}
          {averageLine && (
            <li className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="h-0.5 w-5 bg-ink-soft"
              />
              <span className="text-meta text-ink-soft">
                {AVERAGE_WINDOW}-month average
              </span>
            </li>
          )}
        </ul>
      )}
    </div>
  )
}

export default ColumnChart
