import { describe, expect, it } from 'vitest'
import { compactPrice, counted, formatPrice, pluralise } from './format'

describe('counted', () => {
  // The bug this helper exists for: a listing with one photograph read
  // "1 PHOTOS" on its own detail page, in four places that each solved
  // pluralisation separately and one that did not solve it at all.
  it('does not say "1 photos"', () => {
    expect(counted(1, 'photo')).toBe('1 photo')
    expect(counted(0, 'photo')).toBe('0 photos')
    expect(counted(12, 'photo')).toBe('12 photos')
  })

  it('separates thousands, which a template string loses', () => {
    expect(counted(1248, 'car')).toBe('1,248 cars')
  })

  it('takes an irregular plural', () => {
    expect(counted(1, 'enquiry', 'enquiries')).toBe('1 enquiry')
    expect(counted(3, 'enquiry', 'enquiries')).toBe('3 enquiries')
  })

  it('treats anything unusable as none', () => {
    expect(counted(undefined, 'car')).toBe('0 cars')
    expect(counted(null, 'car')).toBe('0 cars')
  })
})

describe('pluralise', () => {
  it('reads the number, not the string', () => {
    expect(pluralise('1', 'car')).toBe('car')
    expect(pluralise(2, 'car')).toBe('cars')
  })
})

describe('formatPrice', () => {
  it('is KES, and never shows cents on a car', () => {
    const formatted = formatPrice('8900000.00')

    expect(formatted).toContain('KES')
    expect(formatted).toContain('8,900,000')
    expect(formatted).not.toContain('.00')
  })

  it('takes the strings the API actually sends', () => {
    // DRF serialises DecimalField as a string. Every caller passes it
    // straight through.
    expect(formatPrice('5000.00')).toBe(formatPrice(5000))
  })
})

describe('compactPrice', () => {
  it('shortens to something an axis can hold', () => {
    expect(compactPrice(1500000)).toBe('1.5M')
    expect(compactPrice(2000000)).toBe('2M')
    expect(compactPrice(250000)).toBe('250K')
    expect(compactPrice(0)).toBe('0')
  })

  it('takes the strings the API sends', () => {
    expect(compactPrice('8900000.00')).toBe('8.9M')
  })
})
