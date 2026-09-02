import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DealerListings from './DealerListings'
import api from '../../api/client'

vi.mock('../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ isDealer: true }),
}))

const DEALER = {
  id: 1,
  name: 'Westlands Motors',
  listings_live: 2,
  listings_waiting: 1,
}

function listing(overrides = {}) {
  return {
    id: 7,
    make: 'Toyota',
    model: 'Harrier',
    year: 2018,
    price: '3400000.00',
    mileage_km: 78000,
    status: 'submitted',
    status_label: 'Submitted',
    decision_note: '',
    is_editable: true,
    images: [],
    published_car_id: null,
    ...overrides,
  }
}

function show(rows = [listing()]) {
  api.get.mockImplementation((url) => {
    if (url === '/api/dealers/me/') return Promise.resolve({ data: DEALER })
    return Promise.resolve({ data: { results: rows, count: rows.length } })
  })

  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DealerListings />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('DealerListings', () => {
  beforeEach(() => vi.clearAllMocks())

  it('leads with where the dealership stands', async () => {
    show()

    expect(await screen.findByText(/2 cars live/)).toBeInTheDocument()
    expect(screen.getByText(/1 car waiting on us/)).toBeInTheDocument()
  })

  it('names the state for what they are waiting on', async () => {
    // "Waiting on us" is a promise; "Submitted" is a database value.
    show()

    expect(await screen.findByRole('button', { name: 'Waiting on us' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Live on the site' })).toBeInTheDocument()
  })

  it('offers to fix a car that came back, with our reason on it', async () => {
    show([
      listing({
        status: 'rejected',
        status_label: 'Rejected',
        decision_note: 'The photographs are too dark.',
      }),
    ])

    expect(
      await screen.findByText('The photographs are too dark.'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Fix and resend' }),
    ).toBeInTheDocument()
  })

  it('does not offer to edit a car that is already on the site', async () => {
    // It is ours to maintain once it is live, and editing this row would not
    // change the listing a buyer is looking at - two figures for one car.
    show([
      listing({
        status: 'approved',
        status_label: 'Approved',
        is_editable: false,
        published_car_id: 42,
      }),
    ])

    expect(await screen.findByText(/Harrier/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull()
    expect(screen.getByRole('link', { name: 'See it on the site' })).toHaveAttribute(
      'href',
      '/cars/42',
    )
  })

  it('confirms before withdrawing, and says it can come back', async () => {
    api.delete.mockResolvedValue({})
    show()

    await userEvent.click(await screen.findByRole('button', { name: 'Withdraw' }))

    expect(await screen.findByText('Withdraw this car?')).toBeInTheDocument()
    expect(screen.getByText(/submit it again later/)).toBeInTheDocument()
  })

  it('says so plainly when a car has no photographs', async () => {
    show()

    expect(await screen.findByText('No photo')).toBeInTheDocument()
    expect(screen.getByText(/0 photos/)).toBeInTheDocument()
  })

  it('keeps the chosen state in the URL', async () => {
    show()

    await userEvent.click(await screen.findByRole('button', { name: 'Live on the site' }))

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/api/dealers/listings/', {
        params: { status: 'approved' },
      })
    })
  })
})
