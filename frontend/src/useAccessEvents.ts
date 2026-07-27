import { useEffect, useRef, useState } from 'react'
import type { AccessEventMessage, ConnectionStatus } from './types'

const RETRY_DELAY_MS = 3000
const UNAVAILABLE_RETRY_DELAY_MS = 15000

function socketUrl(): string {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${window.location.host}/ws/access-events`
}

/**
 * Keeps the porter screen fed by the access event stream.
 *
 * The socket reconnects on its own because the booth is left unattended: a backend
 * restart or a dropped network must not require someone to reload the screen.
 */
export function useAccessEvents(historyLimit = 9) {
  const [events, setEvents] = useState<AccessEventMessage[]>([])
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const limit = useRef(historyLimit)
  limit.current = historyLimit

  useEffect(() => {
    let socket: WebSocket | null = null
    let retry: number | undefined
    let disposed = false

    const scheduleRetry = (delay: number) => {
      if (!disposed) retry = window.setTimeout(connect, delay)
    }

    function connect() {
      setStatus((current) => (current === 'unavailable' ? current : 'connecting'))
      socket = new WebSocket(socketUrl())

      socket.onopen = () => setStatus('connected')

      socket.onmessage = (message) => {
        const payload = JSON.parse(message.data)
        if (payload.type === 'system_status') {
          setStatus(payload.status === 'monitoring_unavailable' ? 'unavailable' : 'offline')
          return
        }
        if (payload.type !== 'access_event') return
        setStatus('connected')
        const event = payload.data as AccessEventMessage
        setEvents((current) =>
          current.some((seen) => seen.external_id === event.external_id)
            ? current
            : [event, ...current].slice(0, limit.current),
        )
      }

      socket.onclose = () => {
        if (disposed) return
        setStatus((current) => {
          scheduleRetry(current === 'unavailable' ? UNAVAILABLE_RETRY_DELAY_MS : RETRY_DELAY_MS)
          return current === 'unavailable' ? current : 'offline'
        })
      }

      socket.onerror = () => socket?.close()
    }

    connect()
    return () => {
      disposed = true
      window.clearTimeout(retry)
      socket?.close()
    }
  }, [])

  return { events, status }
}
