import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { AuthContext } from './authContext'
import { sendJson, setAuthToken } from './api'

/**
 * Holds the administration session in memory only.
 *
 * Nothing is written to storage on purpose: the machine sits in a guardhouse, so
 * reloading or reopening the application asks for the password again. Moving
 * between the two screens keeps the session, since this lives above the routes.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)

  const signIn = useCallback(async (username: string, password: string) => {
    const session = await sendJson<{ token: string }>('/auth/login', 'POST', { username, password })
    setAuthToken(session.token)
    setToken(session.token)
  }, [])

  const signOut = useCallback(() => {
    // Best effort: the session also has to end on the server, but the screen
    // must lock even if that request cannot be delivered.
    void fetch('/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
    setAuthToken(null)
    setToken(null)
  }, [token])

  const value = useMemo(() => ({ token, signIn, signOut }), [token, signIn, signOut])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
