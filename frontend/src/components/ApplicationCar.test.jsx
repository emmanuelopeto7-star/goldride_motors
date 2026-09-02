import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ApplicationCar from './ApplicationCar'
import api from '../api/client'

vi.mock('../api/client', () => ({
  default: { get: vi.fn() },
}))

const CAR = {
  id: 7,
  make: 'Toyota',
  model: 'Harrier',
  year: 2018,
  price: '3400000.00',
  mileage_km: 78000,
  exterior_colour: 'Pearl white',
  description: 'One owner from new.',
  images: [{ id: 1, image: '/media/dealer-listings/front.jpg' }],
  published_car_id: null,
}

const LOGBOOK = {
  id: 4,
  kind: 'logbook',
  kind_label: 'Logbook',
  filename: 'logbook.pdf',
  size: 82000,
}

function show(props = {}) {
  return render(
    <ApplicationCar cars={[CAR]} documents={[LOGBOOK]} {...props} />,
  )
}

describe('ApplicationCar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    URL.createObjectURL = vi.fn(() => 'blob:fake')
    URL.revokeObjectURL = vi.fn()
  })

  it('shows the car a decision is about', async () => {
    show()

    expect(screen.getByText('2018 Toyota Harrier')).toBeInTheDocument()
    expect(screen.getByText(/3,400,000/)).toBeInTheDocument()
    expect(screen.getByText(/1 photograph/)).toBeInTheDocument()
  })

  it('warns when there is nothing to show a buyer', async () => {
    show({ cars: [{ ...CAR, images: [] }] })

    expect(
      screen.getByText(/Approving lists it without one/),
    ).toBeInTheDocument()
  })

  it('never renders a link to a document', async () => {
    // The download endpoint checks who is asking, which an <a href> cannot
    // carry a token to - and a logbook in a plain URL is a logbook in a
    // browser history and a proxy log.
    const { container } = show()

    for (const anchor of container.querySelectorAll('a')) {
      expect(anchor.getAttribute('href') ?? '').not.toContain('logbook')
      expect(anchor.getAttribute('href') ?? '').not.toContain('media')
    }
    expect(screen.getByRole('button', { name: 'Download' })).toBeInTheDocument()
  })

  it('fetches paperwork through the checked endpoint', async () => {
    api.get.mockResolvedValue({ data: new Blob(['pdf']) })
    show()

    await userEvent.click(screen.getByRole('button', { name: 'Download' }))

    expect(api.get).toHaveBeenCalledWith('/api/staff/dealers/documents/4/', {
      responseType: 'blob',
    })
  })

  it('says so when a file cannot be fetched', async () => {
    api.get.mockRejectedValue(new Error('gone'))
    show()

    await userEvent.click(screen.getByRole('button', { name: 'Download' }))

    expect(
      await screen.findByText('That file could not be fetched.'),
    ).toBeInTheDocument()
  })

  it('marks the paperwork as ours alone', async () => {
    show()

    expect(screen.getByText('Logbook')).toBeInTheDocument()
    expect(
      screen.getByText(/never shown on the site/),
    ).toBeInTheDocument()
  })

  it('copes with an application raised before cars were asked for', async () => {
    show({ cars: [], documents: [] })

    expect(
      screen.getByText(/arrived before we asked for a car/),
    ).toBeInTheDocument()
  })
})
