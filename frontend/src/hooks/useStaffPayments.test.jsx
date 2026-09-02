import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useStaffPayments } from './useStaffPayments'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'

vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../context/AuthContext', () => ({ useAuth: vi.fn() }))

/** These mirror goldride_app/permissions.py, and the whole point of mirroring
 *  is that the two cannot be allowed to drift. A control offered to somebody
 *  the API refuses is a promise the screen breaks; one hidden from somebody
 *  the API allows sends them to find a manager for no reason. */
function asRole({ isSales = false, isManager = false }) {
  useAuth.mockReturnValue({ isSales, isManager })

  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const wrapper = ({ children }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return renderHook(() => useStaffPayments({ status: 'pending' }), { wrapper })
}

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockResolvedValue({ data: { results: [], count: 0 } })
})

describe('who may do what to a payment', () => {
  it('lets Sales raise and chase', () => {
    // Collecting what an agreed order total already says is owed is the job,
    // not a decision about it.
    const { result } = asRole({ isSales: true })

    expect(result.current.canRaise).toBe(true)
    expect(result.current.canDispatch).toBe(true)
  })

  it('does not let Sales say money arrived', () => {
    // A bank transfer has no provider standing behind it - only the person
    // who read the statement - so recording one is a manager's.
    const { result } = asRole({ isSales: true })

    expect(result.current.canRecord).toBe(false)
  })

  it('lets a Manager do all three', () => {
    const { result } = asRole({ isSales: true, isManager: true })

    expect(result.current.canRaise).toBe(true)
    expect(result.current.canDispatch).toBe(true)
    expect(result.current.canRecord).toBe(true)
  })
})

describe('reading the ledger', () => {
  it('asks for the filtered page it was given', async () => {
    asRole({ isSales: true })

    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(api.get).toHaveBeenCalledWith('/api/staff/payments/', {
      params: { status: 'pending' },
    })
  })

  it('copes with an unpaginated list', async () => {
    // Some staff endpoints turn pagination off. The screen reads .results
    // either way rather than branching at every call site.
    api.get.mockResolvedValue({ data: [{ reference: 'a' }] })
    const { result } = asRole({ isSales: true })

    await waitFor(() => expect(result.current.query.data).toBeTruthy())
    expect(result.current.query.data.results).toHaveLength(1)
    expect(result.current.query.data.count).toBe(1)
  })
})
