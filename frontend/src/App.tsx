import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { LandingPage }  from './pages/LandingPage'
import { HomePage }     from './pages/HomePage'
import { SimulatePage } from './pages/SimulatePage'
import { ResultPage }   from './pages/ResultPage'
import { HistoryPage }  from './pages/HistoryPage'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"                    element={<LandingPage />} />
        <Route path="/app"                 element={<HomePage />} />
        <Route path="/demo"                element={<Navigate to="/" replace />} />
        <Route path="/simulate/:simId"     element={<SimulatePage />} />
        <Route path="/result/:simId"       element={<ResultPage />} />
        <Route path="/history"             element={<HistoryPage />} />
        <Route path="*"                    element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
