import { describe, expect, it } from 'vitest'
import {
  SEGMENT_GAP,
  axisTicks,
  columnPath,
  labelledColumns,
  layoutColumns,
  niceCeiling,
  sparklineArea,
  sparklineEnd,
  sparklinePoints,
  trailingAverage,
  yearBoundaries,
} from './chartScale'

const MONTHS = ['Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb']

function series(totals) {
  return totals.map((total, index) => ({ label: MONTHS[index], total }))
}

describe('niceCeiling', () => {
  it('goes to a round number above the data, not to the data', () => {
    expect(niceCeiling(1240000)).toBe(1500000)
    expect(niceCeiling(9)).toBe(10)
    expect(niceCeiling(200)).toBe(200)
  })

  it('has no ceiling for no money', () => {
    expect(niceCeiling(0)).toBe(0)
    expect(niceCeiling(-5)).toBe(0)
    expect(niceCeiling(undefined)).toBe(0)
  })
})

describe('axisTicks', () => {
  it('spans zero to the ceiling', () => {
    expect(axisTicks(1000, 4)).toEqual([0, 250, 500, 750, 1000])
  })

  it('is a single zero when there is nothing to scale', () => {
    expect(axisTicks(0)).toEqual([0])
  })
})

describe('layoutColumns', () => {
  it('gives every month a column, including the empty ones', () => {
    // An axis that starts at the first payment hides how new the business is.
    const { columns } = layoutColumns({ data: series([0, 0, 0, 500, 0, 900]) })

    expect(columns).toHaveLength(6)
    expect(columns[0].segments[0].height).toBe(0)
    expect(columns[3].segments[0].height).toBeGreaterThan(0)
  })

  it('survives a year with no trade at all', () => {
    // The ceiling is zero here, and every height is a division by it.
    const { columns, ceiling } = layoutColumns({ data: series([0, 0, 0, 0, 0, 0]) })

    expect(ceiling).toBe(0)
    for (const column of columns) {
      expect(Number.isFinite(column.segments[0].height)).toBe(true)
      expect(column.segments[0].height).toBe(0)
    }
  })

  it('starts the axis at zero', () => {
    const { columns, baseline, plotHeight, ceiling } = layoutColumns({
      data: series([500, 1000]),
      height: 300,
      padTop: 24,
      padBottom: 28,
    })

    expect(ceiling).toBe(1000)
    // The full-height bar fills the plot; the half-value bar is half of it.
    expect(baseline - columns[1].top).toBeCloseTo(plotHeight, 1)
    expect(baseline - columns[0].top).toBeCloseTo(plotHeight / 2, 1)
  })

  it('never lets a column overflow its ceiling', () => {
    const { columns, baseline, plotHeight } = layoutColumns({
      data: series([1240000, 300000]),
    })

    expect(columns[0].top).toBeGreaterThanOrEqual(baseline - plotHeight)
  })

  it('parts stacked fills without moving the top of the stack', () => {
    const [column] = layoutColumns({
      data: [{ label: 'Feb', card: 400, mpesa: 400, manual: 200 }],
      keys: ['card', 'mpesa', 'manual'],
    }).columns

    const [card, mpesa, manual] = column.segments

    // Each fill above the first gives up exactly the gap, off its bottom edge.
    expect(card.y + card.height).toBeCloseTo(
      layoutColumns({ data: [{ label: 'Feb', card: 400 }], keys: ['card'] })
        .baseline,
      1,
    )
    expect(mpesa.y + mpesa.height + SEGMENT_GAP).toBeCloseTo(card.y, 1)
    expect(manual.y + manual.height + SEGMENT_GAP).toBeCloseTo(mpesa.y, 1)

    // And no two fills occupy the same pixel.
    expect(mpesa.y + mpesa.height).toBeLessThanOrEqual(card.y)
    expect(manual.y + manual.height).toBeLessThanOrEqual(mpesa.y)
  })

  it('rounds only the end of the stack', () => {
    const [column] = layoutColumns({
      data: [{ label: 'Feb', card: 400, mpesa: 400, manual: 200 }],
      keys: ['card', 'mpesa', 'manual'],
    }).columns

    expect(column.segments.map((segment) => segment.rounded)).toEqual([
      false,
      false,
      true,
    ])
  })

  it('rounds the last fill that is actually drawn', () => {
    // The top of the stack is zero here, so the corner belongs to the one
    // below it or the bar ends square in mid-air.
    const [column] = layoutColumns({
      data: [{ label: 'Feb', card: 400, mpesa: 300, manual: 0 }],
      keys: ['card', 'mpesa', 'manual'],
    }).columns

    expect(column.segments[1].rounded).toBe(true)
    expect(column.segments[2].rounded).toBe(false)
  })

  it('keeps columns inside their own band', () => {
    const { columns } = layoutColumns({ data: series([1, 2, 3]), width: 900 })

    for (const column of columns) {
      expect(column.x).toBeGreaterThanOrEqual(column.bandX)
      expect(column.x + column.width).toBeLessThanOrEqual(
        column.bandX + column.bandWidth,
      )
    }
  })

  it('keeps the columns clear of the axis figures', () => {
    // Without the gutter the ticks are drawn at x=0, over whatever the first
    // column happens to be - which looks right until January is a good month.
    const { columns, plotLeft } = layoutColumns({
      data: series([100, 200, 300]),
      width: 1000,
      padLeft: 48,
    })

    expect(plotLeft).toBe(48)
    expect(columns[0].bandX).toBe(48)
    expect(columns[0].x).toBeGreaterThan(48)
    expect(columns.at(-1).x + columns.at(-1).width).toBeLessThanOrEqual(1000)
  })

  it('takes the strings the API actually sends', () => {
    // Money leaves DRF as a string, and "500" + 0 would be "5000".
    const { ceiling } = layoutColumns({
      data: [{ label: 'Jan', total: '500.00' }, { label: 'Feb', total: '250.00' }],
    })

    expect(ceiling).toBe(500)
  })

  it('has no columns and no NaN for no data', () => {
    const { columns, ceiling } = layoutColumns({ data: [] })

    expect(columns).toEqual([])
    expect(ceiling).toBe(0)
  })
})

describe('columnPath', () => {
  it('draws nothing for a month with no trade', () => {
    expect(columnPath(0, 100, 40, 0)).toBe('')
  })

  it('clamps the corner on a stub of a bar rather than inverting it', () => {
    const path = columnPath(0, 100, 40, 2)

    expect(path).not.toContain('NaN')
    expect(path).toContain('M 0 102')
  })
})

describe('labelledColumns', () => {
  it('labels the latest month and the peak, and nothing else', () => {
    const { columns } = layoutColumns({ data: series([100, 900, 200, 300, 0, 400]) })
    const labelled = labelledColumns(columns)

    expect(labelled.has(1)).toBe(true) // the peak
    expect(labelled.has(5)).toBe(true) // the latest month with trade
    expect(labelled.size).toBe(2)
  })

  it('labels nothing when nothing has happened', () => {
    const { columns } = layoutColumns({ data: series([0, 0, 0]) })

    expect(labelledColumns(columns).size).toBe(0)
  })
})

describe('sparklinePoints', () => {
  it('draws a flat line for a flat series instead of NaN', () => {
    const points = sparklinePoints([5, 5, 5], 100, 20)

    expect(points).not.toContain('NaN')
    expect(points).toBe('0,10 50,10 100,10')
  })

  it('puts the low at the bottom and the high at the top', () => {
    const points = sparklinePoints([0, 10], 100, 20).split(' ')

    expect(points[0]).toBe('0,20')
    expect(points[1]).toBe('100,0')
  })

  it('copes with nothing to draw', () => {
    expect(sparklinePoints([], 100, 20)).toBe('')
  })
})

describe('trailingAverage', () => {
  it('waits for a full window rather than averaging what it has', () => {
    // A mean of two months drawn at the same weight as a mean of three is a
    // quiet lie about how much history is behind it.
    expect(trailingAverage([300, 600, 900, 1200], 3)).toEqual([
      null,
      null,
      600,
      900,
    ])
  })

  it('smooths the month one large sale landed in', () => {
    const averages = trailingAverage([0, 0, 9000, 0, 0, 0], 3)

    expect(averages[2]).toBe(3000)
    expect(averages.at(-1)).toBe(0)
  })

  it('takes the strings the API sends, and copes with a short series', () => {
    expect(trailingAverage(['100.00', '200.00', '300.00'], 3)).toEqual([
      null,
      null,
      200,
    ])
    expect(trailingAverage([500], 3)).toEqual([null])
    expect(trailingAverage([], 3)).toEqual([])
  })
})

describe('yearBoundaries', () => {
  it('marks where the calendar year turns over', () => {
    const { columns } = layoutColumns({
      data: [
        { label: 'Nov', year: 2025, total: 0 },
        { label: 'Dec', year: 2025, total: 0 },
        { label: 'Jan', year: 2026, total: 0 },
        { label: 'Feb', year: 2026, total: 0 },
      ],
    })

    const marks = yearBoundaries(columns)
    expect(marks).toHaveLength(1)
    expect(marks[0]).toMatchObject({ index: 2, year: 2026 })
  })

  it('marks nothing inside a single year', () => {
    const { columns } = layoutColumns({
      data: [
        { label: 'Jan', year: 2026, total: 0 },
        { label: 'Feb', year: 2026, total: 0 },
      ],
    })

    expect(yearBoundaries(columns)).toEqual([])
  })
})

describe('sparklineArea', () => {
  it('closes the line down to the baseline', () => {
    const area = sparklineArea([0, 10], 100, 20)

    expect(area.startsWith('M 0,20')).toBe(true)
    expect(area.endsWith('L 100,20 Z')).toBe(true)
    expect(area).not.toContain('NaN')
  })

  it('has nothing to close when there is nothing to draw', () => {
    expect(sparklineArea([], 100, 20)).toBe('')
  })
})

describe('sparklineEnd', () => {
  it('is the last point, which is where the eye is sent', () => {
    expect(sparklineEnd([0, 10], 100, 20)).toEqual({ x: 100, y: 0 })
  })

  it('is nothing for an empty series', () => {
    expect(sparklineEnd([], 100, 20)).toBeNull()
  })
})
