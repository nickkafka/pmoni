import { createContext, useContext } from 'react'

export type Auth = {
  token: string | null
  signIn: (username: string, password: string) => Promise<void>
  signOut: () => void
}

export const AuthContext = createContext<Auth>({
  token: null,
  signIn: async () => {},
  signOut: () => {},
})

export function useAuth(): Auth {
  return useContext(AuthContext)
}
