import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import StaffOverview from './StaffOverview'
import api from '../../api/client'

vi.mock('../../api/client', () => ({
  default: { get: vi.fn() },
}))

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ isManager: true, isSales: true }),
}))

function month(label, year, { card = '0.00', mpesa = '0.00', manual = '0.00', refunded = '0.00' } = {}) {
  const total = [card, mpesa, manual]
    .reduce((sum, part) => sum + Number(part), 0)
    .toFixed(2)
  return { month: `${year}-${label}`, label, year, card, mpesa, manual, refunded, total }
}

const OVERVIEW = {
  generated_at: '2026-08-27T09:00:00Z',
  stock: {
    available_count: 12,
    available_value: '48000000.00',
    reserved_count: 2,
    reserved_value: '9000000.00',
    sold_count: 5,
    without_photo: 30,
    expiring_soon: 3,
  },
  sourcing: { unit_count: 2, capital: '7400000.00' },
  collections: {
    this_month: '900000.00',
    last_month: '600000.00',
    delta_percent: 50.0,
    months: [
      month('Jun', 2026, { card: '600000.00' }),
      month('Jul', 2026, { card: '600000.00' }),
      month('Aug', 2026, { card: '100000.00', mpesa: '200000.00', manual: '600000.00' }),
    ],
  },
  receivables: {
    billed: '20000000.00',
    collected: '4500000.00',
    outstanding: '15500000.00',
    open_orders: 4,
    awaiting_dispatch: 2,
  },
  work: {
    open: 7,
    unclaimed: 3,
    stale_claims: 1,
    by_kind: { approval: 2, sourcing: 1, enquiry: 4 },
    oldest_open_days: 6,
  },
  team: [
    {
      id: 1,
      name: 'Asha',
      username: 'asha',
      role: 'Sales',
      is_active: true,
      tickets_claimed: 2,
      tickets_closed: 9,
      payments_recorded: 3,
    },
    {
      id: 2,
      name: 'Former Colleague',
      username: 'gone',
      role: 'Sales',
      is_active: false,
      tickets_claimed: 0,
      tickets_closed: 41,
      payments_recorded: 0,
    },
  ],
}

function show(overrides = {}) {
  api.get.mockResolvedValue({ data: { ...OVERVIEW, ...overrides } })

  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <StaffOverview />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('StaffOverview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('leads with the four figures the owner opens it for', async () => {
    show()

    expect(await screen.findByText('Collected this month')).toBeInTheDocument()
    expect(screen.getByText(/900,000/)).toBeInTheDocument()
    expect(screen.getByText(/48,000,000/)).toBeInTheDocument()
    expect(screen.getByText(/15,500,000/)).toBeInTheDocument()
    expect(screen.getByText('up 50% on last month')).toBeInTheDocument()
  })

  it('says so in words when there is no month to compare against', async () => {
    // A percentage against zero is not a percentage.
    show({
      collections: { ...OVERVIEW.collections, last_month: '0.00', delta_percent: null },
    })

    expect(await screen.findByText('no month before it')).toBeInTheDocument()
  })

  it('draws a column per month and never a NaN path', async () => {
    const { container } = show()

    await screen.findByText('Collected, month by month')
    const paths = [...container.querySelectorAll('svg path')]

    // Three months, and the last one is a three-method stack.
    expect(paths.length).toBeGreaterThanOrEqual(3)
    for (const path of paths) {
      expect(path.getAttribute('d')).not.toContain('NaN')
    }
  })

  it('keeps the figures readable away from the chart', async () => {
    // Obligatory, not a nicety: the lightest ink step is under the contrast
    // floor, so the numbers have to be legible somewhere that is not a shade.
    show()

    const toggle = await screen.findByRole('button', { name: 'Show the figures' })
    // The team table is always on the page; the month-by-month one is not.
    expect(screen.queryByRole('columnheader', { name: 'Refunded' })).toBeNull()

    await userEvent.click(toggle)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Hide the figures' })).toBeInTheDocument()
    })
    expect(screen.getByRole('columnheader', { name: 'Refunded' })).toBeInTheDocument()
    expect(screen.getAllByText(/Jul 2026/).length).toBeGreaterThan(0)
  })

  it('names every payment method rather than leaving it to the shade', async () => {
    show()

    await screen.findByText('How the money arrives')
    expect(screen.getAllByText('Bank transfer').length).toBeGreaterThan(0)
    expect(screen.getAllByText('M-PESA').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Card').length).toBeGreaterThan(0)
  })

  it('surfaces the claim that was taken and then abandoned', async () => {
    // It exists nowhere else: claiming gates none of the work endpoints, so a
    // stale claim looks exactly like work in progress.
    show()

    const stale = await screen.findByText('Claimed but untouched for two days')
    expect(stale.closest('a')).toHaveAttribute('href', '/staff/tickets')
  })

  it('keeps a deactivated colleague on the roster, marked', async () => {
    show()

    expect(await screen.findByText('Former Colleague')).toBeInTheDocument()
    expect(screen.getByText('Deactivated')).toBeInTheDocument()
    // Their record of what they closed stays readable.
    expect(screen.getByText('41')).toBeInTheDocument()
  })

  it('asks the API for the window in the URL', async () => {
    show()

    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(api.get).toHaveBeenCalledWith('/api/staff/overview/', {
      params: { months: 12 },
    })
  })

  it('offers a way back when the request fails', async () => {
    api.get.mockRejectedValue(new Error('network'))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })

    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <StaffOverview />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(
      await screen.findByText('The overview could not be loaded'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('reads the whole screen from one request', async () => {
    // Six requests would be six loading states, and the figures would arrive
    // out of step with one another.
    show()

    await screen.findByText('The team')
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('renders a fresh install without a single payment', async () => {
    show({
      collections: {
        this_month: '0.00',
        last_month: '0.00',
        delta_percent: null,
        months: [month('Jun', 2026), month('Jul', 2026), month('Aug', 2026)],
      },
    })

    expect(
      await screen.findByText(/Nothing has been collected in this window/),
    ).toBeInTheDocument()
  })
})

describe('StaffOverview accessibility', () => {
  beforeEach(() => vi.clearAllMocks())

  it('describes the chart for a reader who cannot see it', async () => {
    show()

    const chart = await screen.findByRole('img', {
      name: /Money collected over the last 3 months/,
    })
    expect(chart).toBeInTheDocument()
  })

  it('lets a keyboard reach every month', async () => {
    const { container } = show()

    await screen.findByText('Collected, month by month')
    const targets = container.querySelectorAll('svg rect[tabindex="0"]')
    expect(targets).toHaveLength(3)
    expect(within(container).getByLabelText(/Aug 2026/)).toBeInTheDocument()
  })
})
