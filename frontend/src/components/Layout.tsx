import { Suspense, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, BarChart3, Bus, Droplets, FileText, LayoutDashboard, Leaf, LogOut, Menu, Recycle, Settings,
  Trees, Users, Zap,
} from 'lucide-react'
import { get } from '../api'
import { isAdmin, useAuth } from '../store'
import { Loading } from './ui'

interface NavItem {
  to: string
  label: string
  icon: typeof Zap
  admin?: boolean
}

const SECTIONS: [string, NavItem[]][] = [
  ['Overview', [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/operations', label: 'Operations & alerts', icon: Activity },
  ]],
  ['Modules', [
    { to: '/energy', label: 'Energy', icon: Zap },
    { to: '/water', label: 'Water', icon: Droplets },
    { to: '/waste', label: 'Waste', icon: Recycle },
    { to: '/transport', label: 'Transport', icon: Bus },
    { to: '/green', label: 'Green cover', icon: Trees },
  ]],
  ['Intelligence', [
    { to: '/insights', label: 'Forecast & scenarios', icon: BarChart3 },
    { to: '/community', label: 'Community', icon: Users },
    { to: '/reports', label: 'Reports', icon: FileText },
  ]],
  ['Administration', [
    { to: '/settings', label: 'Settings & data', icon: Settings, admin: true },
  ]],
]

const ROLE_LABEL = { admin: 'Administrator', facility: 'Facility team', community: 'Student / Staff' }

export default function Layout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const [lastPath, setLastPath] = useState(location.pathname)
  if (lastPath !== location.pathname) {
    setLastPath(location.pathname)
    setOpen(false)
  }
  const alerts = useQuery({
    queryKey: ['alert-count'],
    queryFn: () => get<{ id: number }[]>('/alerts/', { status: 'open', limit: 99 }),
    refetchInterval: 60000,
  })

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="brand">
          <span className="brand-mark"><Leaf size={19} color="#fff" /></span>
          <span>
            EcoSphere AI
            <small>Smart Campus Sustainability</small>
          </span>
        </div>
        {SECTIONS.map(([label, items]) => {
          const visible = items.filter((i) => !i.admin || isAdmin(user))
          if (!visible.length) return null
          return (
            <div key={label}>
              <div className="nav-label">{label}</div>
              {visible.map(({ to, label: text, icon: Icon }) => (
                <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                  <Icon size={17} />
                  {text}
                  {to === '/operations' && !!alerts.data?.length && <span className="nav-count">{alerts.data.length}</span>}
                </NavLink>
              ))}
            </div>
          )
        })}
        <div className="sidebar-foot">
          <div className="who">{user?.first_name || user?.username}</div>
          <div className="small">{user ? ROLE_LABEL[user.role] : ''}</div>
          <button className="btn sm" style={{ marginTop: 10 }} onClick={logout}>
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button aria-label="Open menu" onClick={() => setOpen(true)}><Menu size={22} /></button>
          <Leaf size={18} /> EcoSphere AI
        </header>
        <main className="content">
          <Suspense fallback={<Loading />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
