import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RaisePaymentModal from './RaisePaymentModal'
import api from '../api/client'

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

const ORDER = {
  id: 9,
  car_description: '2020 Toyota Land Cruiser Prado',
  customer_name: 'newCustomer',
  total_amount: '8900000.00',
  amount_paid: '0.00',
  balance: '8900000.00',
}

/** A stand-in for the page's createPayment mutation.
 *
 *  Handed in as a prop by StaffPayments, so the modal can be driven without
 *  a server: `raises` is what the API would have answered.
 */
function fakeMutation({ raises = null, ...state } = {}) {
  return {
    mutate: vi.fn((_variables, options) => options?.onSuccess?.(raises)),
    reset: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...state,
  }
}

function show(props = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const mutation = props.mutation ?? fakeMutation()

  render(
    <QueryClientProvider client={client}>
      <RaisePaymentModal
        orderId={9}
        mutation={mutation}
        onClose={() => {}}
        onRaised={() => {}}
        {...props}
      />
    </QueryClientProvider>,
  )
  return mutation
}

const amountField = () => screen.getByLabelText(/amount/i)
const raiseButton = () => screen.getByRole('button', { name: /raise it/i })

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockResolvedValue({ data: ORDER })
})

describe('raising a payment against an order', () => {
  it('offers the outstanding balance, because that is usually the ask', async () => {
    show()

    await waitFor(() => expect(amountField()).toHaveValue(8900000))
  })

  it('shows what the amount has to be judged against', async () => {
    show()

    await screen.findByText('Outstanding')
    expect(screen.getAllByText(/8,900,000/).length).toBeGreaterThan(0)
  })
})

describe('the guards on the amount', () => {
  it('refuses more than is outstanding', async () => {
    // A typed amount is a mistyped amount. 89,000,000 for 8,900,000 should
    // not be one keystroke away from a customer's phone.
    show()
    await waitFor(() => expect(amountField()).toHaveValue(8900000))

    await userEvent.clear(amountField())
    await userEvent.type(amountField(), '89000000')

    expect(screen.getByText(/more than is outstanding/i)).toBeInTheDocument()
    expect(raiseButton()).toBeDisabled()
  })

  it('refuses an M-PESA push above the 250,000 ceiling', async () => {
    show()
    await waitFor(() => expect(amountField()).toHaveValue(8900000))

    await userEvent.clear(amountField())
    await userEvent.type(amountField(), '300000')
    await userEvent.selectOptions(screen.getByLabelText(/how they pay/i), 'mpesa')

    expect(screen.getByText(/M-PESA stops at 250,000/i)).toBeInTheDocument()
    expect(raiseButton()).toBeDisabled()
  })

  it('lets an M-PESA payment under the ceiling through', async () => {
    show()
    await waitFor(() => expect(amountField()).toHaveValue(8900000))

    await userEvent.clear(amountField())
    await userEvent.type(amountField(), '200000')
    await userEvent.selectOptions(screen.getByLabelText(/how they pay/i), 'mpesa')

    expect(raiseButton()).toBeEnabled()
  })

  it('leaves an order with no agreed total to the person typing', async () => {
    // A total of 0 means nothing was agreed, not that nothing is owed.
    api.get.mockResolvedValue({
      data: { ...ORDER, total_amount: '0.00', balance: '0.00' },
    })
    show()

    await screen.findByText(/Outstanding/)
    await userEvent.type(amountField(), '450000')

    expect(raiseButton()).toBeEnabled()
  })

  it('warns before the button, not after it', async () => {
    // Raising is not silent any more. Somebody typing an amount should know
    // the customer sees it the moment it is saved.
    show()

    expect(
      await screen.findByText(/told in the chat about this car/i),
    ).toBeInTheDocument()
  })
})

describe('after it is raised', () => {
  const raised = {
    reference: 'abc',
    amount: '5000.00',
    method: 'card',
    order_display: '2020 Toyota Land Cruiser Prado for newCustomer',
    checkout_sent_at: '2026-08-27T09:00:00Z',
  }

  it('says the customer has been told, when there was a thread to tell them in', async () => {
    show({ mutation: fakeMutation({ raises: raised }) })
    await waitFor(() => expect(amountField()).toHaveValue(8900000))

    await userEvent.click(raiseButton())

    expect(await screen.findByText(/been told in the chat/i)).toBeInTheDocument()
  })

  it('says nobody was told, when the order has no thread', async () => {
    // An order raised for a walk-in never had a purchase request behind it,
    // so there is no ticket and nowhere to post.
    show({
      mutation: fakeMutation({ raises: { ...raised, checkout_sent_at: null } }),
    })
    await waitFor(() => expect(amountField()).toHaveValue(8900000))

    await userEvent.click(raiseButton())

    expect(await screen.findByText(/no chat thread/i)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /ask for it now/i }),
    ).toBeInTheDocument()
  })

  it('does not offer to send anything for a bank transfer', async () => {
    show({
      mutation: fakeMutation({ raises: { ...raised, method: 'manual' } }),
    })
    await waitFor(() => expect(amountField()).toHaveValue(8900000))

    await userEvent.click(raiseButton())

    await screen.findByText(/bank transfer/i)
    expect(screen.queryByRole('button', { name: /ask for it now/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /email it as well/i })).toBeNull()
  })
})
