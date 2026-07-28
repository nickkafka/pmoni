import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AccessEventsProvider } from './AccessEventsProvider'
import AdminScreen from './AdminScreen'
import PorterScreen from './PorterScreen'

export default function App() {
  return (
    <AccessEventsProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<PorterScreen />} />
          <Route path="/admin" element={<AdminScreen />} />
        </Routes>
      </BrowserRouter>
    </AccessEventsProvider>
  )
}
