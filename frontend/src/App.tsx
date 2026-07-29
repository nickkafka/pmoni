import { useEffect } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AccessEventsProvider } from './AccessEventsProvider'
import { AuthProvider } from './AuthProvider'
import { ThemeProvider } from './ThemeProvider'
import { onSessionLost } from './api'
import { useAuth } from './authContext'
import AdminScreen from './AdminScreen'
import LoginScreen from './LoginScreen'
import PorterScreen from './PorterScreen'

/**
 * The administration screen is never mounted without a session, so reaching it by
 * typing the address shows the login instead. The API refuses the same routes on
 * its own, so this is convenience rather than the protection itself.
 */
function AdminRoute() {
  const { token, signOut } = useAuth()

  useEffect(() => {
    // A session that expires while the screen is open locks it back.
    onSessionLost(signOut)
    return () => onSessionLost(null)
  }, [signOut])

  return token ? <AdminScreen /> : <LoginScreen />
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AccessEventsProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<PorterScreen />} />
              <Route path="/admin" element={<AdminRoute />} />
            </Routes>
          </BrowserRouter>
        </AccessEventsProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
