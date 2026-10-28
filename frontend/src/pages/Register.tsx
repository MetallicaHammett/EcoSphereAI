import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { api, errorMessage } from '../api'
import { useAuth } from '../store'
import { Field } from '../components/ui'
import { AuthHero } from './Login'

export default function Register() {
  const login = useAuth((s) => s.login)
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', email: '', first_name: '', department: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (key: keyof typeof form) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [key]: e.target.value })

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.post('/auth/register/', form)
      await login(form.username, form.password)
      toast.success('Welcome to EcoSphere AI!')
      navigate('/community', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <AuthHero />
      <div className="auth-panel">
        <div className="auth-card card">
          <h2>Create account</h2>
          <p className="muted" style={{ marginTop: 0 }}>Join the campus sustainability community.</p>
          <form className="form" onSubmit={submit}>
            <Field label="Username"><input value={form.username} onChange={set('username')} required /></Field>
            <Field label="Name"><input value={form.first_name} onChange={set('first_name')} /></Field>
            <Field label="Email"><input type="email" value={form.email} onChange={set('email')} /></Field>
            <Field label="Department / hostel"><input value={form.department} onChange={set('department')} /></Field>
            <Field label="Password (min. 8 characters)">
              <input type="password" value={form.password} onChange={set('password')} required minLength={8}
                autoComplete="new-password" />
            </Field>
            {error && <div className="notice warn">{error}</div>}
            <button className="btn primary" disabled={busy}>{busy ? 'Creating…' : 'Create account'}</button>
          </form>
          <p className="small muted">Already registered? <Link to="/login">Sign in</Link></p>
        </div>
      </div>
    </div>
  )
}
