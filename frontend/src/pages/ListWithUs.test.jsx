import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ListWithUs from './ListWithUs'
import { REQUIRED_DOCUMENTS } from '../hooks/useDealer'
import api from '../api/client'

vi.mock('../api/client', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}))

function show() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ListWithUs />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/** Fill the form as one kind of seller or the other.
 *
 *  `fireEvent.change` rather than `userEvent.type`: typing is per-character,
 *  and eleven fields of it runs past the default timeout in this checkout.
 *  Nothing here depends on keystrokes - the fields are plain controlled
 *  inputs - so a change event exercises the same code for a fraction of the
 *  cost. The clicks below stay real user events.
 */
function fillIn({ dealership = false } = {}) {
  const enter = (label, value) =>
    fireEvent.change(screen.getByLabelText(label), { target: { value } })


  if (dealership) {
    fireEvent.click(screen.getByLabelText('I run a dealership'))
    enter('Dealership', 'Westlands Motors')
  } else {
    enter(/ID or passport number/, '24681012')
  }

  enter('Your name', 'Kamau')
  enter('Email', 'kamau@westlands.co.ke')
  enter('Phone', '0722000000')
  enter('Town or city', 'Nairobi')
  // The car is not optional: approving an application lists it, so staff
  // cannot be asked to decide without one.
  enter('Make', 'Toyota')
  enter('Model', 'Harrier')
  enter('Year', '2018')
  enter('Asking price (KES)', '3400000')
}

/** Attach one file per document the applicant is required to send.
 *
 *  The form will not submit without them, which is the point - so a test that
 *  wants to reach the submit has to do what an applicant does: pick the files,
 *  then say what each one is.
 */
async function attachPaperwork(sellerType) {
  const kinds = REQUIRED_DOCUMENTS[sellerType]
  const files = kinds.map(
    (kind) => new File(['%PDF'], `${kind}.pdf`, { type: 'application/pdf' }),
  )

  await userEvent.upload(screen.getByLabelText(/Add documents/i), files)

  // Everything arrives labelled as the first kind; relabel each in turn.
  kinds.forEach((kind, index) => {
    fireEvent.change(
      screen.getByLabelText(`What ${files[index].name} is`),
      { target: { value: kind } },
    )
  })
}

function send() {
  return userEvent.click(
    screen.getByRole('button', { name: 'Send application' }),
  )
}

/** The body is FormData now, so assertions read it back by key. */
function sent() {
  return api.post.mock.calls[0][1]
}

describe('ListWithUs', () => {
  beforeEach(() => vi.clearAllMocks())

  it('asks a private seller who they are, not what they trade as', async () => {
    show()

    expect(
      screen.getByLabelText(/ID or passport number/),
    ).toBeInTheDocument()
    expect(screen.queryByLabelText('Dealership')).toBeNull()
    expect(screen.queryByLabelText(/Cars to sell/)).toBeNull()
  })

  it('asks a dealership for its name and its fleet', async () => {
    show()

    await userEvent.click(screen.getByLabelText('I run a dealership'))

    expect(screen.getByLabelText('Dealership')).toBeInTheDocument()
    expect(screen.getByLabelText(/Cars to sell/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/ID or passport number/)).toBeNull()
  })

  it('never asks anybody for a website', async () => {
    // It was asked for and never used. A field nobody fills is a field
    // somebody eventually renders on a staff screen as an empty row.
    show()

    expect(screen.queryByLabelText(/website/i)).toBeNull()
    await userEvent.click(screen.getByLabelText('I run a dealership'))
    expect(screen.queryByLabelText(/website/i)).toBeNull()
  })

  it('sends a private seller with their ID and no trading name', async () => {
    api.post.mockResolvedValue({ data: { id: 1 } })
    show()

    fillIn()
    await attachPaperwork('individual')
    await send()

    await waitFor(() => expect(api.post).toHaveBeenCalled())
    expect(api.post.mock.calls[0][0]).toBe('/api/dealers/apply/')
    expect(sent().get('seller_type')).toBe('individual')
    expect(sent().getAll('document_kinds')).toEqual(['id', 'logbook'])
    expect(sent().get('id_number')).toBe('24681012')
    expect(sent().get('dealership_name')).toBeNull()
    // Prefixed, because multipart has no nesting.
    expect(sent().get('car_make')).toBe('Toyota')
    expect(await screen.findByText('Thank you')).toBeInTheDocument()
  })

  it('sends a dealership with its name and fleet', async () => {
    api.post.mockResolvedValue({ data: { id: 1 } })
    show()

    fillIn({ dealership: true })
    await attachPaperwork('dealer')
    await send()

    await waitFor(() => expect(api.post).toHaveBeenCalled())
    expect(sent().get('seller_type')).toBe('dealer')
    expect(sent().get('dealership_name')).toBe('Westlands Motors')
    expect(sent().get('id_number')).toBeNull()
  })

  it('sends no fleet size rather than an empty string', async () => {
    // Omitted rather than sent empty: DRF answers "a valid integer is
    // required" to "", which is a poor thing to read after filling in a form.
    api.post.mockResolvedValue({ data: { id: 1 } })
    show()

    fillIn({ dealership: true })
    await attachPaperwork('dealer')
    await send()

    await waitFor(() => expect(api.post).toHaveBeenCalled())
    expect(sent().get('fleet_size')).toBeNull()
  })

  it('confirms which car is with the team', async () => {
    api.post.mockResolvedValue({ data: { id: 1 } })
    show()

    fillIn()
    await attachPaperwork('individual')
    await send()

    expect(await screen.findByText(/2018 Toyota Harrier/)).toBeInTheDocument()
    expect(screen.getByText(/kamau@westlands.co.ke/)).toBeInTheDocument()
  })

  it('shows what the server objected to', async () => {
    api.post.mockRejectedValue({
      response: { data: { documents: ['That file is larger than 10MB.'] } },
    })
    show()

    fillIn()
    await attachPaperwork('individual')
    await send()

    expect(
      await screen.findByText('That file is larger than 10MB.'),
    ).toBeInTheDocument()
  })

  it('will not send until the required paperwork is attached', async () => {
    // Refused at the door rather than by email a day later: a dealership with
    // no trade licence is not a decision anybody can make.
    show()

    fillIn()
    expect(screen.getByRole('button', { name: 'Send application' })).toBeDisabled()
    expect(screen.getByText(/Still to attach/)).toHaveTextContent(/Logbook/)

    await attachPaperwork('individual')

    expect(
      screen.getByRole('button', { name: 'Send application' }),
    ).toBeEnabled()
    expect(screen.queryByText(/Still to attach/)).toBeNull()
  })

  it('lists what a dealership must send, and ticks each one off', async () => {
    show()

    await userEvent.click(screen.getByLabelText('I run a dealership'))

    for (const label of [
      'Certificate of incorporation or business registration',
      'Trade licence (county permit)',
      "Dealer's application form",
      'Headed application letter',
      'Insurance certificate',
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    // VAT is not on the list: registration only bites above the turnover
    // threshold, so demanding it would refuse every dealer below it.
    expect(screen.queryByText('VAT certificate')).toBeNull()
  })

  it('offers no way to read applications back', async () => {
    // The endpoint is write-only on purpose - a list of who has approached us
    // is a competitor's prospect list - so there is nothing here to poll.
    show()

    expect(screen.queryByRole('button', { name: /check|status/i })).toBeNull()
    expect(api.get).not.toHaveBeenCalled()
  })
})
