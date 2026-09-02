import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { useChatSocket } from './useChatSocket'

/** Adds a message to a cached conversation, once.
 *
 *  Whoever sent it receives it twice - the reply to their own POST, and the
 *  broadcast that went to everyone in the conversation. Keyed on id so the
 *  second one is a no-op rather than a duplicate bubble.
 */
function withMessage(conversation, message) {
  if (!conversation) return conversation
  if (conversation.messages.some((existing) => existing.id === message.id)) {
    return conversation
  }
  return { ...conversation, messages: [...conversation.messages, message] }
}

/** Every thread this customer has - one per ticket.
 *
 *  Chat hangs off the work now, so there is no single conversation to open:
 *  the account lists what they have going and they choose.
 */
export function useMyThreads() {
  return useQuery({
    queryKey: ['chat-threads'],
    queryFn: async () => {
      const res = await api.get('/api/chat/')
      return res.data
    },
  })
}

/** One customer-side conversation, about one ticket. */
export function useMyChat(ticketId, { live = true } = {}) {
  const queryClient = useQueryClient()
  const key = ['chat', 'mine', ticketId]

  const query = useQuery({
    queryKey: key,
    queryFn: async () => {
      const res = await api.get(`/api/chat/${ticketId}/`)
      return res.data
    },
    enabled: Boolean(ticketId),
  })

  useChatSocket(ticketId ? `/ws/chat/${ticketId}/` : null, {
    enabled: live && Boolean(ticketId),
    onMessage: (message) => {
      queryClient.setQueryData(key, (old) => {
        const next = withMessage(old, message)
        // The count has to move with the message. It is derived on the server
        // from read timestamps, so nothing refreshes it until something
        // refetches - and a badge that only appears on reload is the opposite
        // of what a live connection is for.
        if (next === old || !message.from_staff) return next
        return { ...next, unread: (next.unread ?? 0) + 1 }
      })
      queryClient.invalidateQueries({ queryKey: ['chat-threads'] })
    },
    onReconnect: () => queryClient.invalidateQueries({ queryKey: key }),
  })

  const send = useMutation({
    mutationFn: async (body) => {
      const res = await api.post(`/api/chat/${ticketId}/`, { body })
      return res.data
    },
    onSuccess: (message) => {
      queryClient.setQueryData(key, (old) => withMessage(old, message))
      queryClient.invalidateQueries({ queryKey: ['chat-threads'] })
    },
  })

  const markRead = useMutation({
    mutationFn: () => api.post(`/api/chat/${ticketId}/read/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: key })
      queryClient.invalidateQueries({ queryKey: ['chat-threads'] })
    },
  })

  return { query, send, markRead }
}

/** The staff inbox: every conversation somebody has spoken in, whatever the
 *  state of its ticket. A reply to settled work still needs answering. */
export function useChatInbox({ unreadOnly = false, page = 1 } = {}) {
  const params = {}
  if (unreadOnly) params.unread = 'true'
  if (page > 1) params.page = page

  return useQuery({
    queryKey: ['chat-inbox', unreadOnly, page],
    queryFn: async () => {
      const res = await api.get('/api/staff/chats/', { params })
      return res.data
    },
  })
}

/** The staff side of one ticket's conversation. */
export function useStaffChat(ticketId) {
  const queryClient = useQueryClient()
  const key = ['chat', 'staff', ticketId]

  const query = useQuery({
    queryKey: key,
    queryFn: async () => {
      const res = await api.get(`/api/staff/chats/${ticketId}/`)
      return res.data
    },
    enabled: Boolean(ticketId),
  })

  const refreshInbox = () =>
    queryClient.invalidateQueries({ queryKey: ['chat-inbox'] })

  useChatSocket(ticketId ? `/ws/staff/chat/${ticketId}/` : null, {
    enabled: Boolean(ticketId),
    onMessage: (message) => {
      queryClient.setQueryData(key, (old) => withMessage(old, message))
      // The inbox sorts by who spoke last and counts what is unanswered.
      refreshInbox()
    },
    onReconnect: () => queryClient.invalidateQueries({ queryKey: key }),
  })

  const send = useMutation({
    mutationFn: async (body) => {
      const res = await api.post(`/api/staff/chats/${ticketId}/`, { body })
      return res.data
    },
    onSuccess: (message) => {
      queryClient.setQueryData(key, (old) => withMessage(old, message))
      refreshInbox()
    },
  })

  const markRead = useMutation({
    mutationFn: () => api.post(`/api/staff/chats/${ticketId}/read/`),
    onSuccess: refreshInbox,
  })

  return { query, send, markRead }
}
