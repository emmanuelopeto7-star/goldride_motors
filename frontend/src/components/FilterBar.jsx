import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'

// Mirrors the choice lists in cars/models.py. Single source would mean an
// endpoint for them; these change rarely enough to be worth the duplication.
const BODY_TYPES = [
  ['suv', 'SUV'],
  ['pickup', 'Pickup'],
  ['saloon', 'Saloon'],
  ['hatchback', 'Hatchback'],
  ['coupe', 'Coupe'],
  ['van', 'Van'],
  ['convertible', 'Convertible'],
]

const FUEL_TYPES = [
  ['petrol', 'Petrol'],
  ['diesel', 'Diesel'],
  ['hybrid', 'Hybrid'],
  ['electric', 'Electric'],
]

const TRANSMISSIONS = [
  ['automatic', 'Automatic'],
  ['manual', 'Manual'],
]

const SORTS = [
  ['', 'Latest arrivals'],
  ['price', 'Price: low to high'],
  ['-price', 'Price: high to low'],
  ['-year', 'Year: newest'],
  ['mileage_km', 'Mileage: lowest'],
]

/** Closes a panel on an outside click or Escape. */
function useDismiss(ref, onDismiss) {
  useEffect(() => {
    function onPointer(event) {
      if (ref.current && !ref.current.contains(event.target)) onDismiss()
    }
    function onKey(event) {
      if (event.key === 'Escape') onDismiss()
    }

    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)

    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [ref, onDismiss])
}

function Chip({ label, value, options, onChoose }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useDismiss(ref, () => setOpen(false))

  const active = Boolean(value)
  const current = options.find(([key]) => key === value)

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className={`flex h-10 items-center gap-2 rounded-full border px-4 text-[14px] transition-colors ${
          active
            ? 'border-ink bg-ink text-surface'
            : 'border-line hover:border-ink'
        }`}
      >
        {active ? current?.[1] ?? label : label}
        <svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 9l7 7 7-7" stroke="currentColor" strokeWidth="2" fill="none" />
        </svg>
      </button>

      {open && (
        // §3.2: a dropdown is the one place a shadow is allowed.
        <div className="absolute left-0 top-12 z-50 min-w-[200px] border border-line bg-surface py-2 shadow-lg">
          {active && (
            <button
              type="button"
              onClick={() => {
                onChoose('')
                setOpen(false)
              }}
              className="block w-full px-4 py-2 text-left text-meta text-ink-soft hover:bg-page"
            >
              Any {label.toLowerCase()}
            </button>
          )}
          {options.map(([key, text]) => (
            <button
              key={key}
              type="button"
              onClick={() => {
                onChoose(key)
                setOpen(false)
              }}
              className={`block w-full px-4 py-2 text-left text-meta hover:bg-page ${
                key === value ? 'text-ink underline' : 'text-ink'
              }`}
            >
              {text}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function FilterBar() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const { data: makes } = useQuery({
    queryKey: ['makes'],
    queryFn: async () => {
      const res = await api.get('/api/cars/makes/')
      return res.data
    },
  })

  // Every filter change resets to page one - page 3 of the old results is
  // meaningless against the new ones, and may not even exist.
  function setParam(key, value) {
    const params = new URLSearchParams(searchParams)
    if (value) params.set(key, value)
    else params.delete(key)
    params.delete('page')

    const query = params.toString()
    navigate(query ? `/?${query}` : '/')
  }

  const makeOptions = (makes ?? []).map(({ make, count }) => [make, `${make} (${count})`])
  const sortValue = searchParams.get('ordering') ?? ''
  const activeCount = ['make', 'body_type', 'fuel_type', 'transmission'].filter((key) =>
    searchParams.get(key),
  ).length

  return (
    <div className="sticky top-[120px] z-40 border-b border-line bg-surface">
      {/* No overflow-x here: `overflow-x: auto` forces overflow-y to auto too,
          which turns this 64px row into a clipping box and hides every open
          dropdown. Chips wrap on narrow screens instead of scrolling. */}
      <div className="mx-auto flex min-h-16 max-w-[1440px] flex-wrap items-center gap-3 px-5 py-3 lg:px-12">
        <Chip
          label="Make"
          value={searchParams.get('make') ?? ''}
          options={makeOptions}
          onChoose={(value) => setParam('make', value)}
        />
        <Chip
          label="Body"
          value={searchParams.get('body_type') ?? ''}
          options={BODY_TYPES}
          onChoose={(value) => setParam('body_type', value)}
        />
        <Chip
          label="Fuel"
          value={searchParams.get('fuel_type') ?? ''}
          options={FUEL_TYPES}
          onChoose={(value) => setParam('fuel_type', value)}
        />
        <Chip
          label="Gearbox"
          value={searchParams.get('transmission') ?? ''}
          options={TRANSMISSIONS}
          onChoose={(value) => setParam('transmission', value)}
        />

        <div className="ml-auto flex shrink-0 items-center gap-6 pl-6">
          {activeCount > 0 && (
            <button
              type="button"
              onClick={() => navigate('/')}
              className="text-meta text-ink underline"
            >
              Clear all
            </button>
          )}

          {/* §7.4: sort is a text button, never a chip. */}
          <SortMenu
            value={sortValue}
            onChoose={(value) => setParam('ordering', value)}
          />
        </div>
      </div>
    </div>
  )
}

function SortMenu({ value, onChoose }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useDismiss(ref, () => setOpen(false))

  const current = SORTS.find(([key]) => key === value) ?? SORTS[0]

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex items-center gap-2 whitespace-nowrap text-meta text-ink underline"
      >
        {current[1]}
        <svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 9l7 7 7-7" stroke="currentColor" strokeWidth="2" fill="none" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-8 z-50 min-w-[200px] border border-line bg-surface py-2 shadow-lg">
          {SORTS.map(([key, text]) => (
            <button
              key={key || 'default'}
              type="button"
              onClick={() => {
                onChoose(key)
                setOpen(false)
              }}
              className={`block w-full px-4 py-2 text-left text-meta hover:bg-page ${
                key === value ? 'underline' : ''
              }`}
            >
              {text}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default FilterBar
