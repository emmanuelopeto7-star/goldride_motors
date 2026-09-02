/** Chart geometry, kept out of the components so it can be tested.
 *
 *  Charts do not break by rendering the wrong colour. They break on an axis
 *  that divides by zero in a month with no trade, a stack whose segments
 *  overlap by a pixel, and a bar that runs off the top because the ceiling was
 *  the largest value rather than a round number above it. All of that is
 *  arithmetic with no DOM in it, so it lives here and has tests.
 *
 *  The mark rules are deliberate, not styling: fills never touch (a 2px gap of
 *  the surface between them, so two dark segments read as two), the rounded
 *  corner goes on the data end only and never on the baseline, and the axis
 *  always starts at zero - a truncated axis on a bar chart misstates the
 *  comparison the bars exist to make.
 */

/** Column width as a share of its band. Below about half the columns read as
 *  a line chart drawn badly; above about three quarters they touch. */
export const BAND_FILL = 0.62

/** The surface gap between one fill and the next. */
export const SEGMENT_GAP = 2

/** Rounded data end. Never applied to the baseline corner. */
export const CORNER = 4

/** Under this a column is a sliver and the corner radius eats it. */
export const MIN_COLUMN = 6

function round(value) {
  return Math.round(value * 100) / 100
}

/** The first round number at or above `value`.
 *
 *  An axis topped at the largest data point puts that bar flush against the
 *  frame and gives the reader nothing to divide by. 1,240,000 tops out at
 *  1.5M, which is a number somebody can hold in their head.
 */
export function niceCeiling(value) {
  const target = Number(value)
  if (!Number.isFinite(target) || target <= 0) return 0

  const magnitude = 10 ** Math.floor(Math.log10(target))
  const steps = [1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10]

  for (const step of steps) {
    const candidate = step * magnitude
    if (candidate >= target) return round(candidate)
  }
  return round(10 * magnitude)
}

/** Gridline values, bottom to top. Four gaps is enough to read against and
 *  few enough to stay recessive. */
export function axisTicks(max, count = 4) {
  if (!(max > 0)) return [0]
  return Array.from({ length: count + 1 }, (_, index) =>
    round((max / count) * index),
  )
}

/** An SVG path for one column: square on the baseline, rounded at the data end.
 *
 *  A `rect` with `rx` rounds all four corners, which detaches the bar from its
 *  own axis. Returns an empty string for a column with no height, so a month
 *  with no trade draws nothing rather than a 0px artefact.
 */
export function columnPath(x, y, width, height, radius = CORNER) {
  if (!(height > 0) || !(width > 0)) return ''

  const r = Math.min(radius, width / 2, height)
  const left = round(x)
  const right = round(x + width)
  const top = round(y)
  const bottom = round(y + height)

  return [
    `M ${left} ${bottom}`,
    `L ${left} ${round(top + r)}`,
    `Q ${left} ${top} ${round(left + r)} ${top}`,
    `L ${round(right - r)} ${top}`,
    `Q ${right} ${top} ${right} ${round(top + r)}`,
    `L ${right} ${bottom}`,
    'Z',
  ].join(' ')
}

/** Lay out a stacked column chart.
 *
 *  `keys` are stacked bottom to top in the order given, so the order is the
 *  legend's order too. One key is the ordinary case - a single series is a
 *  stack of one, which keeps the single-series and split charts on the same
 *  code path instead of two that drift apart.
 *
 *  Every entry in `data` gets a column, including empty months: an axis that
 *  starts at the first month with trade hides how new the business is.
 */
export function layoutColumns({
  data = [],
  keys = ['total'],
  width = 1000,
  height = 300,
  padTop = 24,
  padBottom = 28,
  // Room for the axis figures. Without it they are drawn at x=0, on top of
  // whatever the first column happens to be that month - which looks fine on
  // the data you built it against and collides the moment January is a good
  // month.
  padLeft = 0,
  max,
}) {
  const plotHeight = Math.max(0, height - padTop - padBottom)
  const plotWidth = Math.max(0, width - padLeft)
  const baseline = padTop + plotHeight

  const totals = data.map((entry) =>
    keys.reduce((sum, key) => sum + (Number(entry[key]) || 0), 0),
  )
  const ceiling = max ?? niceCeiling(Math.max(0, ...totals))

  const band = data.length > 0 ? plotWidth / data.length : 0
  const columnWidth =
    band > 0 ? Math.max(MIN_COLUMN, Math.min(band * BAND_FILL, band - 2)) : 0

  // Guarded rather than assumed: a fresh install, or any 12 months without a
  // payment, makes the ceiling zero and every division below it NaN.
  const scale = ceiling > 0 ? plotHeight / ceiling : 0

  const columns = data.map((entry, index) => {
    const bandX = padLeft + band * index
    const x = bandX + (band - columnWidth) / 2

    let stacked = 0
    const segments = []

    keys.forEach((key, position) => {
      const value = Number(entry[key]) || 0
      const full = value * scale
      const top = baseline - stacked - full

      // The gap is taken off the bottom of every segment above the first, so
      // the stack keeps its true top and only the fills are parted.
      const trimmed = position === 0 ? full : full - SEGMENT_GAP

      segments.push({
        key,
        value,
        x: round(x),
        y: round(top),
        width: round(columnWidth),
        height: round(Math.max(0, trimmed)),
      })

      stacked += full
    })

    const drawn = segments.filter((segment) => segment.height > 0)
    const topmost = drawn.length > 0 ? drawn[drawn.length - 1] : null

    return {
      ...entry,
      index,
      total: totals[index],
      x: round(x),
      width: round(columnWidth),
      bandX: round(bandX),
      bandWidth: round(band),
      centreX: round(bandX + band / 2),
      top: round(baseline - stacked),
      segments: segments.map((segment) => ({
        ...segment,
        // Only the segment that ends the stack gets the rounded data end.
        rounded: topmost !== null && segment === topmost,
      })),
    }
  })

  return {
    ceiling,
    baseline: round(baseline),
    plotHeight: round(plotHeight),
    plotLeft: round(padLeft),
    // Exposed so a second mark - an average line, a target - can be drawn
    // against the same scale instead of inventing its own.
    yFor: (value) => round(baseline - (Number(value) || 0) * scale),
    ticks: axisTicks(ceiling).map((value) => ({
      value,
      y: round(baseline - value * scale),
    })),
    columns,
  }
}

/** A trailing mean, one entry per input, `null` until there is enough history.
 *
 *  Twelve columns of a lumpy business are hard to read a direction out of -
 *  one 8.9M car lands and the shape of the year is that car. The average is
 *  the trend the columns are too noisy to show, and null rather than a partial
 *  mean for the first months, because averaging two months and drawing it at
 *  the same weight as a real one is a quiet lie.
 */
export function trailingAverage(values, window = 3) {
  const numbers = values.map((value) => Number(value) || 0)

  return numbers.map((_, index) => {
    if (index < window - 1) return null
    const slice = numbers.slice(index - window + 1, index + 1)
    return round(slice.reduce((sum, value) => sum + value, 0) / window)
  })
}

/** Where the calendar year changes, for a divider on the axis.
 *
 *  A twelve-month window nearly always spans a new year, and "Jan" landing
 *  between "Dec" and "Feb" with nothing to mark it reads as one continuous
 *  year until somebody works out that it cannot be.
 */
export function yearBoundaries(columns) {
  return columns
    .map((column, index) =>
      index > 0 && column.year !== columns[index - 1].year
        ? { index, year: column.year, x: round(column.bandX) }
        : null,
    )
    .filter(Boolean)
}

/** Which columns carry a number printed above them.
 *
 *  Never all of them - a value on every column is a table pretending to be a
 *  chart. The last month because it is the one being asked about, and the
 *  peak because it is the only other one a reader looks for.
 */
export function labelledColumns(columns) {
  const withTrade = columns.filter((column) => column.total > 0)
  if (withTrade.length === 0) return new Set()

  const latest = withTrade[withTrade.length - 1]
  const peak = withTrade.reduce((best, column) =>
    column.total > best.total ? column : best,
  )

  return new Set([latest.index, peak.index])
}

/** The same series as a filled area, closed to the baseline.
 *
 *  A 2px line alone in a tile reads as an afterthought; the fill gives the
 *  trend a shape at the size a stat tile actually offers it. Solid, not a
 *  gradient - DESIGN.md 2.2.
 */
export function sparklineArea(values, width, height) {
  const points = sparklinePoints(values, width, height)
  if (!points) return ''

  const parts = points.split(' ')
  const first = parts[0].split(',')[0]
  const last = parts[parts.length - 1].split(',')[0]

  return `M ${first},${height} L ${points.replace(/ /g, ' L ')} L ${last},${height} Z`
}

/** The last point of the sparkline, for the dot that marks where it got to. */
export function sparklineEnd(values, width, height) {
  const points = sparklinePoints(values, width, height)
  if (!points) return null

  const [x, y] = points.split(' ').pop().split(',')
  return { x: Number(x), y: Number(y) }
}

/** A polyline through the values, fitted to a small box. Flat line for a flat
 *  series, rather than the divide-by-zero that would otherwise put it at NaN. */
export function sparklinePoints(values, width, height) {
  const numbers = values.map((value) => Number(value) || 0)
  if (numbers.length === 0) return ''
  if (numbers.length === 1) return `0,${round(height / 2)} ${width},${round(height / 2)}`

  const high = Math.max(...numbers)
  const low = Math.min(...numbers)
  const span = high - low

  return numbers
    .map((value, index) => {
      const x = (width / (numbers.length - 1)) * index
      const y = span === 0 ? height / 2 : height - ((value - low) / span) * height
      return `${round(x)},${round(y)}`
    })
    .join(' ')
}
