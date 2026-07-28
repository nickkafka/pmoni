import type { ReactNode } from 'react'
import { AccessEventsContext } from './accessEventsContext'
import { useAccessEvents } from './useAccessEvents'

/**
 * Holds the event stream above the routes.
 *
 * The porter screen unmounts while the operator works in the administration
 * screen. Owning the connection here keeps it open across that navigation, so
 * passages that happen meanwhile are still received and the screen comes back
 * showing them instead of an empty board.
 */
export function AccessEventsProvider({ children }: { children: ReactNode }) {
  const stream = useAccessEvents()
  return <AccessEventsContext.Provider value={stream}>{children}</AccessEventsContext.Provider>
}
