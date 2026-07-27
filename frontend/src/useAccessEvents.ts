import { useEffect, useRef, useState } from 'react'
import type { AccessEventMessage, ConnectionStatus } from './types'

const FIRST_RETRY_MS = 1000
const MAX_RETRY_MS = 15000

function socketUrl(): string {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${window.location.host}/ws/access-events`
}

/**
 * Each device numbers its own journal, so a serial only identifies a passage
 * together with the device it came from. Keying on the serial alone would drop a
 * real passage as a duplicate whenever two devices reached the same number.
 */
function keyOf(event: AccessEventMessage): string {
  return `${event.device_id}:${event.external_id}`
}

/**
 * Keeps the porter screen fed by the access event stream.
 *
 * The booth is left unattended, so the socket has to come back on its own after a
 * backend restart or a dropped network: every failure path schedules another
 * attempt, and the screen also retries as soon as the machine reports it is online
 * again or the operator brings the window back to the front.
 */
export function useAccessEvents(historyLimit = 9) {
  const [events, setEvents] = useState<AccessEventMessage[]>([])
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const limit = useRef(historyLimit)
  limit.current = historyLimit

  useEffect(() => {
    let socket: WebSocket | null = null
    let timer: number | undefined
    let attempt = 0
    let disposed = false

    function scheduleRetry() {
      if (disposed) return
      window.clearTimeout(timer)
      const delay = Math.min(FIRST_RETRY_MS * 2 ** attempt, MAX_RETRY_MS)
      attempt += 1
      timer = window.setTimeout(connect, delay)
    }

    function connect() {
      if (disposed) return
      window.clearTimeout(timer)
      setStatus('connecting')

      let unavailable = false
      let current: WebSocket
      try {
        current = new WebSocket(socketUrl())
      } catch {
        // A constructor failure must not end the loop: without this the screen
        // would stay dead until someone reloaded the page.
        scheduleRetry()
        return
      }
      socket = current

      current.onopen = () => {
        attempt = 0
        setStatus('connected')
      }

      current.onmessage = (message) => {
        const payload = JSON.parse(message.data)
        if (payload.type === 'system_status') {
          unavailable = payload.status === 'monitoring_unavailable'
          setStatus(unavailable ? 'unavailable' : 'offline')
          return
        }
        if (payload.type !== 'access_event') return
        const event = payload.data as AccessEventMessage
        setEvents((known) =>
          known.some((seen) => keyOf(seen) === keyOf(event))
            ? known
            : [event, ...known].slice(0, limit.current),
        )
      }

      current.onerror = () => current.close()

      current.onclose = () => {
        if (disposed || socket !== current) return
        setStatus(unavailable ? 'unavailable' : 'offline')
        scheduleRetry()
      }
    }

    function reconnectNow() {
      if (disposed || socket?.readyState === WebSocket.OPEN) return
      attempt = 0
      connect()
    }

    const onVisible = () => {
      if (document.visibilityState === 'visible') reconnectNow()
    }

    connect()
    window.addEventListener('online', reconnectNow)
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      disposed = true
      window.clearTimeout(timer)
      window.removeEventListener('online', reconnectNow)
      document.removeEventListener('visibilitychange', onVisible)
      socket?.close()
    }
  }, [])

  return { events, status }
}
