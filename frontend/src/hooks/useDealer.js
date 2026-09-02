import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

/** Everything a dealership touches, on both sides of being approved.
 *
 *  The public half needs no account and deliberately cannot read anything
 *  back - applying is write-only at the API, so there is no "check my
 *  application" query here to write against.
 */

export const LISTING_STATES = [
  ['submitted', 'Waiting on us'],
  ['approved', 'Live on the site'],
  ['rejected', 'Needs changes'],
  ['withdrawn', 'Withdrawn'],
]

/** The paperwork an application can carry. Mirrors DealerDocument.KIND_CHOICES.
 *
 *  The dealership list is what Kenya actually requires of a motor vehicle
 *  dealer, rather than a generic "attach something": naming each document is
 *  what lets the form say which one is missing instead of leaving somebody to
 *  guess after a refusal.
 */
export const DOCUMENT_KINDS = [
  ['business_reg', 'Certificate of incorporation or business registration'],
  ['kra_pin', 'KRA PIN certificate'],
  ['vat', 'VAT certificate'],
  ['trade_licence', 'Trade licence (county permit)'],
  ['id', 'National ID or passport'],
  ['dealer_form', "Dealer's application form"],
  ['letter', 'Headed application letter'],
  ['insurance', 'Insurance certificate'],
  ['logbook', 'Logbook'],
  ['import_entry', 'Import entry'],
  ['other', 'Other'],
]

/** What an application is refused without. Mirrors
 *  DealerDocument.REQUIRED_OF_DEALERSHIP / REQUIRED_OF_INDIVIDUAL.
 *
 *  Duplicated from the backend on purpose, the same way the import age rule
 *  is: the server is the authority and refuses either way, but telling
 *  somebody what is still missing while they are filling the form in is far
 *  better than telling them after they press send.
 *
 *  VAT is deliberately not required - registration only bites above the
 *  turnover threshold, so demanding it would refuse every dealer below it.
 */
export const REQUIRED_DOCUMENTS = {
  dealer: [
    'business_reg',
    'kra_pin',
    'trade_licence',
    'id',
    'dealer_form',
    'letter',
    'insurance',
  ],
  individual: ['id', 'logbook'],
}

export function missingDocuments(sellerType, documents) {
  const attached = new Set(documents.map((entry) => entry.kind))
  return (REQUIRED_DOCUMENTS[sellerType] ?? []).filter(
    (kind) => !attached.has(kind),
  )
}

/** Who is applying. Mirrors DealerApplication.SELLER_CHOICES.
 *
 *  The two are asked for different things because they are different: a person
 *  has one car and an ID, a business has a fleet and a trading name. The type
 *  is sent rather than guessed from which fields were filled in.
 */
export const SELLER_TYPES = [
  ['individual', 'Selling my own car'],
  ['dealer', 'I run a dealership'],
]

export const MAX_PHOTOS = 12
export const MAX_DOCUMENTS = 14

/** Ask to list with Goldride, with the first car and its paperwork. Public.
 *
 *  Multipart, not JSON: files and fields travel together so the whole thing
 *  either arrives or does not. The car fields go up prefixed because multipart
 *  has no nesting - the server gathers `car_make` and friends back into one
 *  object and validates them with the same serializer the portal uses.
 */
export function useApplyToList() {
  return useMutation({
    mutationFn: async ({ car = {}, photos = [], documents = [], ...fields }) => {
      const body = new FormData()

      for (const [key, value] of Object.entries(fields)) {
        if (value !== null && value !== undefined && value !== '') {
          body.append(key, value)
        }
      }
      for (const [key, value] of Object.entries(car)) {
        if (value !== null && value !== undefined && value !== '') {
          body.append(`car_${key}`, value)
        }
      }
      for (const file of photos) body.append('photos', file)
      for (const entry of documents) {
        body.append('documents', entry.file)
        // Positional: multipart has no other way to pair a label with a file,
        // so the two lists must stay the same length and order.
        body.append('document_kinds', entry.kind)
      }

      const res = await api.post('/api/dealers/apply/', body)
      return res.data
    },
  })
}

/** Whether an invitation link is still good, before showing the form. */
export function useActivationLink(token) {
  return useQuery({
    queryKey: ['dealer-activation', token],
    queryFn: async () => {
      const res = await api.get(`/api/dealers/activate/${token}/`)
      return res.data
    },
    enabled: Boolean(token),
    // An expired link will not become valid by asking again.
    retry: false,
  })
}

export function useSetDealerPassword(token) {
  return useMutation({
    mutationFn: async (password) => {
      const res = await api.post(`/api/dealers/activate/${token}/`, { password })
      return res.data
    },
  })
}

export function useDealerProfile() {
  const { isDealer } = useAuth()

  return useQuery({
    queryKey: ['dealer-me'],
    queryFn: async () => {
      const res = await api.get('/api/dealers/me/')
      return res.data
    },
    enabled: isDealer,
  })
}

/** The dealership's own submissions. Scoped by the account, never by a param. */
export function useDealerListings({ status = '' } = {}) {
  const queryClient = useQueryClient()
  const { isDealer } = useAuth()

  const query = useQuery({
    queryKey: ['dealer-listings', status],
    queryFn: async () => {
      const params = status ? { status } : {}
      const res = await api.get('/api/dealers/listings/', { params })
      const data = res.data
      return Array.isArray(data) ? { results: data, count: data.length } : data
    },
    enabled: isDealer,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['dealer-listings'] })
    queryClient.invalidateQueries({ queryKey: ['dealer-me'] })
  }

  const create = useMutation({
    mutationFn: async (values) => {
      const res = await api.post('/api/dealers/listings/', values)
      return res.data
    },
    onSuccess: invalidate,
  })

  const update = useMutation({
    mutationFn: async ({ id, ...values }) => {
      const res = await api.patch(`/api/dealers/listings/${id}/`, values)
      return res.data
    },
    onSuccess: invalidate,
  })

  const withdraw = useMutation({
    mutationFn: async (id) => {
      await api.delete(`/api/dealers/listings/${id}/`)
      return id
    },
    onSuccess: invalidate,
  })

  const addPhoto = useMutation({
    mutationFn: async ({ id, file }) => {
      const body = new FormData()
      body.append('image', file)
      const res = await api.post(`/api/dealers/listings/${id}/images/`, body)
      return res.data
    },
    onSuccess: invalidate,
  })

  const removePhoto = useMutation({
    mutationFn: async ({ id, imageId }) => {
      await api.delete(`/api/dealers/listings/${id}/images/${imageId}/`)
    },
    onSuccess: invalidate,
  })

  return { query, create, update, withdraw, addPhoto, removePhoto }
}
