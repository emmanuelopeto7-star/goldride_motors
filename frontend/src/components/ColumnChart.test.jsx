import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import ColumnChart from './ColumnChart'

const SERIES = [
  { key: 'card', label: 'Card', shade: 'ink' },
  { key: 'mpesa', label: 'M-PESA', shade: 'soft' },
  { key: 'manual', label: 'Bank transfer', shade: 'mute' },
]

function months() {
  const labels = ['Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug']
  return labels.map((label, index) => ({
    month: `2026-${index}`,
    label,
    year: 2026,
    card: index === 11 ? '100000.00' : '0.00',
    mpesa: index === 11 ? '200000.00' : '0.00',
    manual: index === 11 ? '600000.00' : index === 0 ? '50000.00' : '0.00',
    refunded: index === 11 ? '25000.00' : '0.00',
    total: index === 11 ? '900000.00' : index === 0 ? '50000.00' : '0.00',
  }))
}

function draw(data = months()) {
  return render(
    <ColumnChart data={data} series={SERIES} caption="Money collected." />,
  )
}

function bands(container) {
  return [...container.querySelectorAll('svg rect[tabindex="0"]')]
}

describe('ColumnChart', () => {
  it('names the month and the figure on hover', async () => {
    const { container } = draw()

    await userEvent.hover(bands(container).at(-1))

    expect(await screen.findByText(/Aug 2026/)).toBeInTheDocument()
    expect(screen.getByText(/900,000/)).toBeInTheDocument()
  })

  it('breaks the total down by method, named not shaded', async () => {
    const { container } = draw()

    await userEvent.hover(bands(container).at(-1))

    // Scoped to the tooltip: the legend names the methods too, which is the
    // point of having one.
    const tooltip = (await screen.findByText(/Aug 2026/)).parentElement
    expect(within(tooltip).getByText('Bank transfer')).toBeInTheDocument()
    expect(within(tooltip).getByText(/600,000/)).toBeInTheDocument()
  })

  it('mentions a refund only where there was one', async () => {
    const { container } = draw()

    await userEvent.hover(bands(container).at(-1))
    expect(await screen.findByText(/25,000 refunded/)).toBeInTheDocument()

    await userEvent.hover(bands(container)[5])
    expect(screen.queryByText(/refunded/)).toBeNull()
  })

  it('keeps the tooltip inside the panel at either edge', async () => {
    // Centred on the last column it hangs off the side of the card, which is
    // only visible in a browser at the width the dashboard actually uses.
    const { container } = draw()

    await userEvent.hover(bands(container).at(-1))
    const atEnd = await screen.findByText(/Aug 2026/)
    expect(atEnd.parentElement.className).toContain('-translate-x-full')

    await userEvent.hover(bands(container)[0])
    const atStart = await screen.findByText('Sep 2026')
    expect(atStart.parentElement.className).not.toContain('translate-x')

    await userEvent.hover(bands(container)[5])
    const middle = await screen.findByText('Feb 2026')
    expect(middle.parentElement.className).toContain('-translate-x-1/2')
  })

  it('lets an empty month be hovered too', async () => {
    // The bar is nothing, so the hit target has to be the whole band or the
    // reader cannot ask what happened in a month where nothing did.
    const { container } = draw()

    await userEvent.hover(bands(container)[4])

    expect(await screen.findByText('Jan 2026')).toBeInTheDocument()
    // The total, and each of the three methods under it, all read zero.
    // (Queried rather than read off textContent: Intl puts a non-breaking
    // space inside "KES 0".)
    expect(screen.getAllByText('KES 0')).toHaveLength(4)
  })

  it('draws a single-series chart without a breakdown', async () => {
    const { container } = render(
      <ColumnChart
        data={months()}
        series={[{ key: 'total', label: 'Collected', shade: 'ink' }]}
        caption="Money collected."
      />,
    )

    await userEvent.hover(bands(container).at(-1))

    expect(await screen.findByText(/Aug 2026/)).toBeInTheDocument()
    // One series needs no key: the heading already names it.
    expect(screen.queryByText('Bank transfer')).toBeNull()
  })
})

describe('ColumnChart, the marks beyond the columns', () => {
  it('marks the month still in progress rather than letting it read as a slump', async () => {
    // Three weeks of trade standing against twelve finished months.
    const { container } = draw()

    expect(screen.getByText('SO FAR')).toBeInTheDocument()
    expect(container.querySelectorAll('rect[stroke-dasharray]')).toHaveLength(1)

    await userEvent.hover(bands(container).at(-1))
    expect(await screen.findByText(/so far/)).toBeInTheDocument()
  })

  it('says nothing about a partial month when the window has ended', async () => {
    const { container } = render(
      <ColumnChart data={months()} series={SERIES} caption="x" lastIsPartial={false} />,
    )

    expect(screen.queryByText('SO FAR')).toBeNull()
    expect(container.querySelectorAll('rect[stroke-dasharray]')).toHaveLength(0)
  })

  it('draws the trailing average over the columns, and names it', () => {
    const { container } = draw()

    const line = container.querySelector('polyline')
    expect(line).not.toBeNull()
    expect(line.getAttribute('points')).not.toContain('NaN')
    // Ten points for twelve months: the first two have no window behind them.
    expect(line.getAttribute('points').split(' ')).toHaveLength(10)
    expect(screen.getByText('3-month average')).toBeInTheDocument()
  })

  it('gives the average in the tooltip, where the figure is', async () => {
    const { container } = draw()

    await userEvent.hover(bands(container).at(-1))

    const tooltip = (await screen.findByText(/Aug 2026/)).parentElement
    expect(within(tooltip).getByText(/3-month average/)).toBeInTheDocument()
  })

  it('divides the years, so Jan does not read as the same one as Dec', () => {
    const data = months().map((month, index) => ({
      ...month,
      year: index < 4 ? 2025 : 2026,
    }))

    draw(data)

    expect(screen.getByText('2026')).toBeInTheDocument()
  })

  it('names every series in a legend, not only in the tooltip', () => {
    // Identity must never rest on a shade: ink-mute is under the contrast
    // floor against the surface.
    draw()

    const legend = screen.getByRole('list')
    expect(legend.textContent).toContain('Card')
    expect(legend.textContent).toContain('M-PESA')
    expect(legend.textContent).toContain('Bank transfer')
  })

  it('has no series legend for a single series', () => {
    render(
      <ColumnChart
        data={months()}
        series={[{ key: 'total', label: 'Collected', shade: 'ink' }]}
        caption="x"
      />,
    )

    // The heading names it; a one-row key is furniture.
    const legend = screen.getByRole('list')
    expect(legend.textContent).not.toContain('Bank transfer')
    expect(legend.textContent).toContain('3-month average')
  })
})
