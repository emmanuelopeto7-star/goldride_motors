import { describe, expect, it } from 'vitest'
import { errorMessages } from './errors'

const FALLBACK = 'Something went wrong. Please try again.'

function refusal(data) {
  return { response: { data } }
}

describe('errorMessages', () => {
  it('reads DRF field errors', () => {
    const messages = errorMessages(
      refusal({ amount: ['An amount to collect has to be more than nothing.'] }),
    )

    expect(messages).toEqual(['An amount to collect has to be more than nothing.'])
  })

  it('flattens several fields into one list', () => {
    const messages = errorMessages(
      refusal({ order: ['Required.'], amount: ['Required.', 'Too small.'] }),
    )

    expect(messages).toHaveLength(3)
  })

  it('drops `code`, which is for us and not for the reader', () => {
    // Without this a refusal renders its own machine name underneath the
    // sentence explaining it - "protected" sitting under a good reason.
    const messages = errorMessages(
      refusal({ code: 'protected', detail: 'This order still holds payments.' }),
    )

    expect(messages).toEqual(['This order still holds payments.'])
  })

  it('never shows an HTML error page raw', () => {
    expect(errorMessages(refusal('<!doctype html><h1>502 Bad Gateway'))).toEqual([
      FALLBACK,
    ])
  })

  it('never shows a wall of text raw', () => {
    expect(errorMessages(refusal('x'.repeat(400)))).toEqual([FALLBACK])
  })

  it('shows a short plain-text refusal as written', () => {
    expect(errorMessages(refusal('Too many requests.'))).toEqual([
      'Too many requests.',
    ])
  })

  it('falls back when there is no response at all', () => {
    // A network failure, a timeout, an aborted request.
    expect(errorMessages(new Error('Network Error'))).toEqual([FALLBACK])
    expect(errorMessages(undefined)).toEqual([FALLBACK])
  })
})
