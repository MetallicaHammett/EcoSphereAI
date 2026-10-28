import type { ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { errorMessage } from '../api'
import { usePeriod, type Period } from '../store'

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="row no-print">{actions}</div>}
    </div>
  )
}

export function Card({ title, subtitle, actions, children, className = '' }: {
  title?: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}

export function Stat({ label, value, unit, sub, icon }: {
  label: string
  value: ReactNode
  unit?: string
  sub?: ReactNode
  icon?: ReactNode
}) {
  return (
    <div className="card stat">
      <span className="stat-label">
        {icon}
        {label}
      </span>
      <span className="stat-value">
        {value}
        {unit && <small>{unit}</small>}
      </span>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  )
}

export function Loading({ label = 'Loading data…' }: { label?: string }) {
  return (
    <div className="state">
      <div className="spinner" />
      <span>{label}</span>
    </div>
  )
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div className="state">
      <AlertTriangle size={28} color="var(--danger)" />
      <span>{errorMessage(error)}</span>
      {retry && (
        <button className="btn" onClick={retry}>
          <RefreshCw size={14} /> Try again
        </button>
      )}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="state">{children}</div>
}

const PERIODS: [Period, string][] = [
  ['7', '7 days'],
  ['30', '30 days'],
  ['90', '90 days'],
  ['ytd', 'Year to date'],
]

export function PeriodPicker() {
  const { period, setPeriod } = usePeriod()
  return (
    <div className="segmented" role="group" aria-label="Reporting period">
      {PERIODS.map(([value, label]) => (
        <button key={value} className={period === value ? 'on' : ''} onClick={() => setPeriod(value)}>
          {label}
        </button>
      ))}
    </div>
  )
}

export function Segmented<T extends string>({ value, options, onChange }: {
  value: T
  options: [T, string][]
  onChange: (v: T) => void
}) {
  return (
    <div className="segmented">
      {options.map(([v, label]) => (
        <button key={v} className={value === v ? 'on' : ''} onClick={() => onChange(v)}>
          {label}
        </button>
      ))}
    </div>
  )
}

export function Badge({ kind, children }: { kind?: string; children: ReactNode }) {
  return <span className={`badge ${kind ?? ''}`}>{children}</span>
}

export function Progress({ value }: { value: number }) {
  return (
    <div className="progress" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
      <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  )
}

export function Stars({ count }: { count: number }) {
  return (
    <span className="stars" aria-label={`${count} of 5 stars`}>
      {'★'.repeat(count)}
      <span style={{ color: '#d8dfdb' }}>{'★'.repeat(5 - count)}</span>
    </span>
  )
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      {label}
      {children}
    </label>
  )
}
