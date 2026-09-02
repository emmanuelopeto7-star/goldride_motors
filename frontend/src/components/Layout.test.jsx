import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Layout from './Layout'

vi.mock('../api/client', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: { results: [] } }) },
}))

const auth = {
  user: null,
  isSales: false,
  isDealer: false,
  signOut: vi.fn(),
}

vi.mock('../context/AuthContext', () => ({
  useAuth: () => auth,
}))

function show(path = '/cars/1') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Layout />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('the header route for dealers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    auth.user = null
    auth.isDealer = false
    auth.isSales = false
  })

  it('offers a visitor a way to list their cars', async () => {
    // It used to exist only in the footer, which is a poor place for the one
    // thing a visiting dealership came to do.
    show()

    const link = await screen.findByRole('link', { name: 'List your cars' })
    expect(link).toHaveAttribute('href', '/list-with-us')
  })

  it('sends a signed-in dealer to their own cars instead', async () => {
    auth.user = { username: 'kamau' }
    auth.isDealer = true
    show()

    expect(
      await screen.findByRole('link', { name: 'Your cars' }),
    ).toHaveAttribute('href', '/dealer')
    expect(screen.queryByRole('link', { name: 'List your cars' })).toBeNull()
  })

  it('gives the header links a focus ring and a real hit target', async () => {
    // A 13px link showing focus only as a browser default outline is unusable
    // by keyboard over a photographic hero.
    show()

    const link = await screen.findByRole('link', { name: 'List your cars' })

    expect(link.className).toContain('focus-visible:outline')
    expect(link.className).toContain('py-3')
  })

  it('underlines the page you are on, and only that one', async () => {
    // §2.1 gives underline to links *and active states*. Underlining all of
    // them permanently said every link was the current page, and left no mark
    // for the one that actually was.
    show('/import')

    const here = await screen.findByRole('link', { name: 'Import a car' })
    const elsewhere = screen.getByRole('link', { name: 'List your cars' })

    expect(here.className).toContain('underline')
    expect(here.className).toContain('text-ink')

    expect(elsewhere.className).not.toMatch(/(^|\s)underline(\s|$)/)
    expect(elsewhere.className).toContain('text-ink-soft')
    // Still discoverable as a link on the way to it.
    expect(elsewhere.className).toContain('hover:underline')
  })

  it('keeps the footer route as well', async () => {
    show()

    const links = await screen.findAllByRole('link', {
      name: /list your cars/i,
    })
    expect(links.length).toBeGreaterThan(1)
  })
})
