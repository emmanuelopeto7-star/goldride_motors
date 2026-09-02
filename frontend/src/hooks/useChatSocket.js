import { useEffect, useRef } from 'react'
import { getToken } from '../lib/auth'
import { socketUrl } from '../lib/socket'

const FIRST_RETRY_MS = 500
const LONGEST_RETRY_MS = 15000

/** Holds a websocket open, and puts it back when it drops.
 *
 *  `onReconnect` matters as much as `onMessage`. The server's broadcast is
 *  best-effort - it is sent after the message is already saved and never
 *  fails the write - so anything said while the socket was down is in the
 *  database but was never pushed. Refetching on every reconnect is what makes
 *  a dropped connection a delay rather than a hole in the transcript.
 */
export function useChatSocket(path, { enabled = true, onMessage, onReconnect }) {
  const handlers = useRef({ onMessage, onReconnect })
  handlers.current = { onMessage, onReconnect }

  useEffect(() => {
    if (!enabled || !path) return undefined

    let socket
    let retry
    let attempts = 0
    let deliberate = false

    function open() {
      // The token rides as a subprotocol rather than in the query string:
      // query strings are logged by proxies, and these tokens never expire.
      socket = new WebSocket(socketUrl(path), ['token', getToken()])

      socket.onopen = () => {
        if (attempts > 0) handlers.current.onReconnect?.()
        attempts = 0
      }

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.message) handlers.current.onMessage?.(data.message)
        } catch {
          // A frame we cannot read is not worth tearing the socket down for.
        }
      }

      socket.onclose = () => {
        if (deliberate) return
        attempts += 1
        const wait = Math.min(FIRST_RETRY_MS * 2 ** attempts, LONGEST_RETRY_MS)
        retry = setTimeout(open, wait)
      }
    }

    open()

    return () => {
      deliberate = true
      clearTimeout(retry)
      socket?.close()
    }
  }, [path, enabled])
}
