import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CorrectPaymentModal from './CorrectPaymentModal'

vi.mock('../api/client', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ isSales: true, isManager: true }),
}))

const PAYMENT = {
  reference: 'abc-123',
  amount: '250000.00',
  method: 'card',
  method_label: 'Card',
  status: 'paid',
}

function fakeMutation(state = {}) {
  return {
    mutate: vi.fn((_variables, options) => options?.onSuccess?.()),
    reset: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    ...state,
  }
}

function show(mutation = fakeMutation()) {
  render(
    <CorrectPaymentModal
      payment={PAYMENT}
      mutation={mutation}
      onClose={() => {}}
    />,
  )
  return mutation
}

describe('CorrectPaymentModal', () => {
  beforeEach(() => vi.clearAllMocks())

  it('says what the payment is now, so nobody corrects the wrong one', () => {
    show()

    expect(screen.getByText(/250,000/)).toBeInTheDocument()
    expect(screen.getByText(/currently/)).toHaveTextContent('paid')
  })

  it('does not offer the state it is already in', () => {
    show()

    const options = [...screen.getByRole('combobox').options].map((o) => o.value)
    expect(options).not.toContain('paid')
    expect(options).toContain('refunded')
  })

  it('will not submit without a real reason', async () => {
    // The history is what somebody reads six months later when a customer
    // disputes it, and "fixed" tells them nothing.
    const mutation = show()

    await userEvent.type(screen.getByLabelText(/^Why/), 'oops')

    expect(screen.getByRole('button', { name: 'Correct it' })).toBeDisabled()
    expect(mutation.mutate).not.toHaveBeenCalled()
  })

  it('sends the correction with its reason', async () => {
    const mutation = show()

    await userEvent.selectOptions(screen.getByRole('combobox'), 'refunded')
    await userEvent.type(
      screen.getByLabelText(/^Why/),
      'refunded at the bank on the 14th',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Correct it' }))

    expect(mutation.mutate).toHaveBeenCalledWith(
      {
        reference: 'abc-123',
        status: 'refunded',
        reason: 'refunded at the bank on the 14th',
      },
      expect.anything(),
    )
  })

  it('warns that the reason is kept for good', () => {
    show()

    expect(screen.getByText(/with your name against it/)).toBeInTheDocument()
  })

  it('stays open and explains when the server refuses', () => {
    show(
      fakeMutation({
        isError: true,
        error: { response: { data: { error: 'already refunded' } } },
      }),
    )

    expect(screen.getByText('already refunded')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Correct it' })).toBeInTheDocument()
  })
})
