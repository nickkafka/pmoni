import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { AuthContext } from './authContext'
import { sendJson, setAuthToken } from './api'

const STORAGE_KEY = 'pmoni.admin-token'

function readStored(): string | null {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function store(token: string | null): void {
  try {
    if (token) window.sessionStorage.setItem(STORAGE_KEY, token)
    else window.sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // Sem armazenamento a sessão ainda funciona; só não sobrevive ao recarregar.
  }
}

/**
 * Holds the administration session for the life of the window.
 *
 * Kept in `sessionStorage` rather than in memory, so reloading the page does not
 * ask for the password in the middle of a task — and not in `localStorage`, so
 * closing the window or the application still locks it: the machine sits in a
 * guardhouse, and whoever opens it next must not find the administration unlocked.
 *
 * The server keeps sessions in memory, so a stored token can outlive the one it
 * names after a restart. It is checked once on load, and dropped if refused.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => {
    const stored = readStored()
    setAuthToken(stored)
    return stored
  })

  const forget = useCallback(() => {
    store(null)
    setAuthToken(null)
    setToken(null)
  }, [])

  useEffect(() => {
    if (!token) return
    // Só na montagem: a partir daqui, qualquer 401 já tranca a tela pelo api.ts.
    fetch('/auth/session', { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => {
        if (response.status === 401) forget()
      })
      .catch(() => {
        // Backend fora do ar não prova que a sessão acabou; a próxima chamada decide.
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const signIn = useCallback(async (username: string, password: string) => {
    const session = await sendJson<{ token: string }>('/auth/login', 'POST', { username, password })
    store(session.token)
    setAuthToken(session.token)
    setToken(session.token)
  }, [])

  const signOut = useCallback(() => {
    // Best effort: the session also has to end on the server, but the screen
    // must lock even if that request cannot be delivered.
    void fetch('/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${token}` } })
    forget()
  }, [token, forget])

  const value = useMemo(() => ({ token, signIn, signOut }), [token, signIn, signOut])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
