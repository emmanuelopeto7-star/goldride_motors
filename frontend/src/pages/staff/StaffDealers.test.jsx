import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import StaffDealers from './StaffDealers'
import api from '../../api/client'

vi.mock('../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

const auth = { isSales: true, isManager: true }
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => auth,
}))

const SUBMISSION = {
  id: 5,
  make: 'Toyota',
  model: 'Harrier',
  year: 2018,
  price: '3400000.00',
  status: 'submitted',
  status_label: 'Submitted',
  dealer_name: 'Westlands Motors',
  description: '',
  decision_note: '',
  images: [],
  published_car_id: null,
  is_editable: true,
}

const APPLICATION = {
  id: 3,
  dealership_name: 'Westlands Motors',
  contact_name: 'Kamau',
  email: 'kamau@westlands.co.ke',
  phone: '0722000000',
  location: 'Nairobi',
  fleet_size: 24,
  website: '',
  message: 'We have 24 units.',
  status: 'pending',
  decision_note: '',
  reviewed_by_name: null,
}

function show(path = '/staff/dealers') {
  api.get.mockImplementation((url) => {
    if (url.includes('applications')) {
      return Promise.resolve({ data: { results: [APPLICATION], count: 1 } })
    }
    if (url.includes('listings')) {
      return Promise.resolve({ data: { results: [SUBMISSION], count: 1 } })
    }
    return Promise.resolve({ data: { results: [], count: 0 } })
  })

  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <StaffDealers />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('StaffDealers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    auth.isSales = true
    auth.isManager = true
  })

  it('opens on the cars waiting to be published', async () => {
    show()

    expect(await screen.findByText(/Harrier/)).toBeInTheDocument()
    expect(screen.getByText(/Westlands Motors/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Publish' })).toBeInTheDocument()
  })

  it('warns before publishing a car with no photographs', async () => {
    show()

    expect(
      await screen.findByText(/Publishing puts it on the site without one/),
    ).toBeInTheDocument()
  })

  it('sends the decision with the note the dealer will read', async () => {
    api.post.mockResolvedValue({ data: {} })
    show()

    await userEvent.type(
      await screen.findByPlaceholderText('Why, if you are rejecting it'),
      'Photos too dark',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Reject' }))

    expect(api.post).toHaveBeenCalledWith(
      '/api/staff/dealers/listings/5/reject/',
      { note: 'Photos too dark' },
    )
  })

  it('lets sales read but never decide', async () => {
    // Taking on a dealership and publishing somebody else's car are both
    // commitments; the API refuses either way, this only hides the control.
    auth.isManager = false
    show()

    expect(await screen.findByText(/Harrier/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Publish' })).toBeNull()
    expect(screen.getByText('A manager decides this one.')).toBeInTheDocument()
  })

  it('says what approving an application actually does', async () => {
    show('/staff/dealers?tab=applications')

    expect(await screen.findByText(/Kamau/)).toBeInTheDocument()
    expect(
      screen.getByText(/creates their account, emails them a link/),
    ).toBeInTheDocument()
    // The part that is new and easy to miss: it also lists the car.
    expect(
      screen.getByText(/puts the car above on the site immediately/),
    ).toBeInTheDocument()
  })

  it('does not carry one tab’s filter into the other', async () => {
    // The two lists filter the same param over different values, so "pending"
    // would land the submissions list on a state it has never heard of.
    show('/staff/dealers?tab=submissions&status=withdrawn')

    await screen.findByRole('button', { name: 'Applications' })
    await userEvent.click(screen.getByRole('button', { name: 'Applications' }))

    const calls = api.get.mock.calls.filter(([url]) => url.includes('applications'))
    expect(calls.at(-1)[1]).toEqual({ params: { status: 'pending' } })
  })
})
