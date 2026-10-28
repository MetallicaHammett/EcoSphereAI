import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Leaf, LogIn } from 'lucide-react'
import { errorMessage } from '../api'
import { useAuth } from '../store'
import { Field } from '../components/ui'

const DEMO = [
  ['admin', 'admin123', 'Administrator / sustainability officer'],
  ['facility', 'facility123', 'Facility operations team'],
  ['student', 'student123', 'Student / staff community'],
]

export function AuthHero() {
  return (
    <div className="auth-hero">
      <div className="row"><span className="brand-mark"><Leaf size={20} color="#fff" /></span><b>EcoSphere AI</b></div>
      <h1>Smart Campus Sustainability &amp; Carbon Footprint Monitoring</h1>
      <p>What is measured gets managed. Near real-time electricity, water, waste, transport and green-cover data,
        converted into GHG Protocol emissions for the whole campus.</p>
      <ul>
        <li>Live IoT metering with automatic leak and after-hours detection</li>
        <li>Scope 1, 2 and 3 carbon engine with version-controlled factors</li>
        <li>Forecasting, benchmarking and what-if scenario modelling</li>
        <li>Community leaderboards and personal commute footprint</li>
      </ul>
    </div>
  )
}

export default function Login() {
  const login = useAuth((s) => s.login)
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e?: FormEvent, creds?: [string, string]) {
    e?.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(creds?.[0] ?? username, creds?.[1] ?? password)
      navigate('/', { replace: true })
    } catch (err) {
      const message = errorMessage(err)
      setError(message.includes('No active account') ? 'Incorrect username or password.' : message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <AuthHero />
      <div className="auth-panel">
        <div className="auth-card card">
          <h2>Sign in</h2>
          <p className="muted" style={{ marginTop: 0 }}>Use your campus account.</p>
          <form className="form" onSubmit={submit}>
            <Field label="Username">
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required autoFocus />
            </Field>
            <Field label="Password">
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password" required />
            </Field>
            {error && <div className="notice warn">{error}</div>}
            <button className="btn primary" disabled={busy}><LogIn size={15} /> {busy ? 'Signing in…' : 'Sign in'}</button>
          </form>
          <p className="small muted">New student or staff member? <Link to="/register">Create an account</Link></p>
          <div className="demo-logins">
            <span className="small muted">Demo accounts (seeded test data):</span>
            {DEMO.map(([u, p, label]) => (
              <button key={u} className="btn sm" disabled={busy} onClick={() => submit(undefined, [u, p])}>
                <span>{label}</span><b>{u}</b>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
