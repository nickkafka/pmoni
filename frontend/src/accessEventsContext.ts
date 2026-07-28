import { createContext, useContext } from 'react'
import type { AccessEventMessage, ConnectionStatus } from './types'

export type AccessEvents = {
  events: AccessEventMessage[]
  status: ConnectionStatus
}

export const AccessEventsContext = createContext<AccessEvents>({
  events: [],
  status: 'connecting',
})

export function useAccessEventStream(): AccessEvents {
  return useContext(AccessEventsContext)
}
