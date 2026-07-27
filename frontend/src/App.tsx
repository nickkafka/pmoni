import { BrowserRouter, Route, Routes } from 'react-router-dom'
import AdminScreen from './AdminScreen'
import PorterScreen from './PorterScreen'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PorterScreen />} />
        <Route path="/admin" element={<AdminScreen />} />
      </Routes>
    </BrowserRouter>
  )
}
