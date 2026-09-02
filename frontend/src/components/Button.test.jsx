import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import Button from './Button'

function show(props = {}, children = 'Do the thing') {
  return render(
    <MemoryRouter>
      <Button {...props}>{children}</Button>
    </MemoryRouter>,
  )
}

describe('Button', () => {
  it('never submits a form by accident', () => {
    // type defaults to "submit" inside a form, which has surprised somebody on
    // every project that did not set it.
    show()

    expect(screen.getByRole('button')).toHaveAttribute('type', 'button')
  })

  it('carries the focus ring so no call site has to remember it', () => {
    // §4.7 was in DESIGN.md and only ever reached the header, because it lived
    // on the call sites rather than on the button.
    show()

    expect(screen.getByRole('button').className).toContain(
      'focus-visible:outline',
    )
  })

  it('rings a filled button in ink, not in its own white text', () => {
    // The ring sits outside the fill, on the page behind it.
    show({ variant: 'primary' })

    expect(screen.getByRole('button').className).toContain(
      'focus-visible:outline-ink',
    )
  })

  it('follows the text colour on an outlined one, so it inverts for free', () => {
    show({ variant: 'secondary' })

    expect(screen.getByRole('button').className).toContain(
      'focus-visible:outline-current',
    )
  })

  it('centres a route with flex rather than a padding guess', () => {
    // The old `pt-3.5` broke the moment a label wrapped to two lines.
    show({ to: '/cars' })

    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', '/cars')
    expect(link.className).toContain('items-center')
    expect(link.className).not.toContain('pt-3.5')
  })

  it('keeps the two agreed sizes and nothing in between', () => {
    const { rerender } = show({ size: 'default' })
    expect(screen.getByRole('button').className).toContain('h-11')

    rerender(
      <MemoryRouter>
        <Button size="large">Do the thing</Button>
      </MemoryRouter>,
    )
    expect(screen.getByRole('button').className).toContain('h-12')
  })

  it('is a plain underlined link when the action is reversible', () => {
    show({ variant: 'quiet' })

    const button = screen.getByRole('button')
    expect(button.className).toContain('underline')
    expect(button.className).not.toContain('bg-ink')
  })

  it('passes everything else through', async () => {
    const onClick = vi.fn()
    show({ onClick, disabled: true, 'aria-label': 'Publish' })

    expect(screen.getByRole('button', { name: 'Publish' })).toBeDisabled()
  })
})
