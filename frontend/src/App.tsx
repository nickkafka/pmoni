import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AccessEventsProvider } from './AccessEventsProvider'
import { ThemeProvider } from './ThemeProvider'
import AdminScreen from './AdminScreen'
import PorterScreen from './PorterScreen'

export default function App() {
  return (
    <ThemeProvider>
      <AccessEventsProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<PorterScreen />} />
            <Route path="/admin" element={<AdminScreen />} />
          </Routes>
        </BrowserRouter>
      </AccessEventsProvider>
    </ThemeProvider>
  )
}
