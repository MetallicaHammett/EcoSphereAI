import { lazy, useEffect, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import Layout from './components/Layout'
import { Loading } from './components/ui'
import { isAdmin, useAuth } from './store'
import Login from './pages/Login'
import Register from './pages/Register'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Operations = lazy(() => import('./pages/Operations'))
const Energy = lazy(() => import('./pages/Energy'))
const Water = lazy(() => import('./pages/Water'))
const Waste = lazy(() => import('./pages/Waste'))
const Transport = lazy(() => import('./pages/Transport'))
const Green = lazy(() => import('./pages/Green'))
const Insights = lazy(() => import('./pages/Insights'))
const Community = lazy(() => import('./pages/Community'))
const Reports = lazy(() => import('./pages/Reports'))
const Admin = lazy(() => import('./pages/Admin'))

function Protected({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth()
  if (!ready) return <Loading label="Starting…" />
  return user ? children : <Navigate to="/login" replace />
}

export default function App() {
  const { load, logout, user, ready } = useAuth()
  const queryClient = useQueryClient()

  useEffect(() => {
    load()
    const onLogout = () => logout()
    window.addEventListener('eco:logout', onLogout)
    return () => window.removeEventListener('eco:logout', onLogout)
  }, [load, logout])

  useEffect(() => {
    if (!user) queryClient.clear()
  }, [user, queryClient])

  return (
    <Routes>
      <Route path="/login" element={ready && user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/register" element={ready && user ? <Navigate to="/" replace /> : <Register />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route index element={<Dashboard />} />
        <Route path="operations" element={<Operations />} />
        <Route path="energy" element={<Energy />} />
        <Route path="water" element={<Water />} />
        <Route path="waste" element={<Waste />} />
        <Route path="transport" element={<Transport />} />
        <Route path="green" element={<Green />} />
        <Route path="insights" element={<Insights />} />
        <Route path="community" element={<Community />} />
        <Route path="reports" element={<Reports />} />
        <Route path="settings" element={isAdmin(user) ? <Admin /> : <Navigate to="/" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
