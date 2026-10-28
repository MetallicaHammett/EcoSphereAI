import { useEffect, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { api, errorMessage, get } from '../api'
import type { Building, Factor, Meter } from '../types'
import type { User } from '../store'
import { Badge, Card, ErrorState, Field, Loading, PageHeader, Stat } from '../components/ui'
import { dateTime, localISODate, num, timeAgo } from '../format'

type Tab = 'settings' | 'factors' | 'buildings' | 'devices' | 'quality' | 'users'

const TABS: [Tab, string][] = [
  ['settings', 'Campus & targets'], ['factors', 'Emission factors'], ['buildings', 'Buildings'],
  ['devices', 'Meters & gateways'], ['quality', 'Data quality'], ['users', 'Users & roles'],
]

export default function Admin() {
  const [tab, setTab] = useState<Tab>('settings')
  return (
    <>
      <PageHeader title="Settings & data management"
        subtitle="Organisational boundary, version-controlled emission factors, devices and access control." />
      <div className="tabs">
        {TABS.map(([k, l]) => <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === 'settings' && <SettingsTab />}
      {tab === 'factors' && <FactorsTab />}
      {tab === 'buildings' && <BuildingsTab />}
      {tab === 'devices' && <DevicesTab />}
      {tab === 'quality' && <QualityTab />}
      {tab === 'users' && <UsersTab />}
    </>
  )
}

function useInvalidateAll() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries()
}

// ------------------------------------------------------------------ settings & targets

interface CampusSettings {
  name: string
  student_count: number
  staff_count: number
  baseline_year: number
  electricity_tariff: number
  diesel_price: number
  water_tariff: number
  green_power_share: number
  boundary_notes: string
}

interface TargetRow {
  id: number
  name: string
  baseline_year: number
  baseline_tco2e: number
  target_year: number
  reduction_pct: number
  target_tco2e: number
}

function SettingsTab() {
  const invalidate = useInvalidateAll()
  const q = useQuery({ queryKey: ['settings'], queryFn: () => get<CampusSettings>('/settings/') })
  const targets = useQuery({ queryKey: ['targets'], queryFn: () => get<TargetRow[]>('/targets/') })
  const [form, setForm] = useState<CampusSettings | null>(null)
  useEffect(() => {
    if (q.data) setForm(q.data)
  }, [q.data])
  const save = useMutation({
    mutationFn: (body: CampusSettings) => api.put('/settings/', body),
    onSuccess: () => {
      toast.success('Settings saved')
      invalidate()
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  if (q.isLoading || !form) return q.isError ? <ErrorState error={q.error} retry={q.refetch} /> : <Loading />
  const numField = (key: keyof CampusSettings, label: string, step = '1') => (
    <Field label={label}>
      <input type="number" step={step} min="0" value={String(form[key])}
        onChange={(e) => setForm({ ...form, [key]: e.target.value === '' ? 0 : Number(e.target.value) })} />
    </Field>
  )
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate(form)
  }

  return (
    <div className="grid cols-2">
      <Card title="Campus profile & boundary" subtitle="Used for per-capita KPIs, costs and the GHG report">
        <form className="form" onSubmit={submit}>
          <Field label="Institution / campus name"><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></Field>
          <div className="form-row">
            {numField('student_count', 'Students')}
            {numField('staff_count', 'Staff')}
            {numField('baseline_year', 'Baseline year')}
          </div>
          <div className="form-row">
            {numField('electricity_tariff', 'Electricity ₹/kWh', '0.01')}
            {numField('diesel_price', 'Diesel ₹/L', '0.01')}
            {numField('water_tariff', 'Water ₹/kL', '0.01')}
          </div>
          <Field label="Certified green power share (0–1) for market-based Scope 2">
            <input type="number" min="0" max="1" step="0.01" value={form.green_power_share}
              onChange={(e) => setForm({ ...form, green_power_share: Number(e.target.value) })} />
          </Field>
          <Field label="Organisational boundary notes">
            <textarea rows={3} value={form.boundary_notes} onChange={(e) => setForm({ ...form, boundary_notes: e.target.value })} />
          </Field>
          <button className="btn primary" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save settings'}</button>
        </form>
      </Card>
      <TargetsCard rows={targets.data ?? []} loading={targets.isLoading} />
    </div>
  )
}

function TargetsCard({ rows, loading }: { rows: TargetRow[]; loading: boolean }) {
  const invalidate = useInvalidateAll()
  const [form, setForm] = useState({ name: '', baseline_year: '2025', baseline_tco2e: '', target_year: '2030', reduction_pct: '45' })
  const add = useMutation({
    mutationFn: () => api.post('/targets/', {
      name: form.name, baseline_year: Number(form.baseline_year), baseline_tco2e: Number(form.baseline_tco2e),
      target_year: Number(form.target_year), reduction_pct: Number(form.reduction_pct),
    }),
    onSuccess: () => {
      toast.success('Target added')
      setForm({ ...form, name: '', baseline_tco2e: '' })
      invalidate()
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/targets/${id}/`),
    onSuccess: () => invalidate(),
    onError: (e) => toast.error(errorMessage(e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    add.mutate()
  }
  return (
    <Card title="Reduction targets" subtitle="Set after the baseline assessment, not assumed in advance">
      {loading ? <Loading /> : (
        <div className="list" style={{ marginBottom: 16 }}>
          {rows.map((t) => (
            <div className="list-item" key={t.id}>
              <div style={{ flex: 1 }}>
                <b>{t.name}</b>
                <div className="small muted">−{t.reduction_pct}% from {num(t.baseline_tco2e)} t ({t.baseline_year}) to {num(t.target_tco2e)} t by {t.target_year}</div>
              </div>
              <button className="btn sm danger" onClick={() => confirm('Delete this target?') && remove.mutate(t.id)}>Delete</button>
            </div>
          ))}
          {!rows.length && <p className="muted">No targets yet.</p>}
        </div>
      )}
      <form className="form" onSubmit={submit}>
        <Field label="Target name"><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required placeholder="Net-zero pathway 2040" /></Field>
        <div className="form-row">
          <Field label="Baseline year"><input type="number" value={form.baseline_year} onChange={(e) => setForm({ ...form, baseline_year: e.target.value })} required /></Field>
          <Field label="Baseline tCO₂e"><input type="number" min="1" value={form.baseline_tco2e} onChange={(e) => setForm({ ...form, baseline_tco2e: e.target.value })} required /></Field>
          <Field label="Target year"><input type="number" value={form.target_year} onChange={(e) => setForm({ ...form, target_year: e.target.value })} required /></Field>
          <Field label="Reduction %"><input type="number" min="1" max="100" value={form.reduction_pct} onChange={(e) => setForm({ ...form, reduction_pct: e.target.value })} required /></Field>
        </div>
        <button className="btn" disabled={add.isPending}>Add target</button>
      </form>
    </Card>
  )
}

// ------------------------------------------------------------------ factors

const ACTIVITIES: [string, string, number, string][] = [
  ['electricity_grid', 'Grid electricity', 2, 'kWh'], ['diesel', 'Diesel', 1, 'L'], ['petrol', 'Petrol', 1, 'L'],
  ['lpg', 'LPG', 1, 'kg'], ['refrigerant_r410a', 'Refrigerant R-410A', 1, 'kg'], ['refrigerant_r32', 'Refrigerant R-32', 1, 'kg'],
  ['refrigerant_r22', 'Refrigerant R-22', 1, 'kg'], ['water_supply', 'Water supply and treatment', 3, 'kL'],
  ['waste_landfill', 'Waste to landfill', 3, 'kg'], ['waste_recycled', 'Waste recycled', 3, 'kg'],
  ['waste_composted', 'Waste composted', 3, 'kg'], ['waste_biogas', 'Waste to biogas', 3, 'kg'],
  ['waste_incinerated', 'Waste incinerated', 3, 'kg'], ['commute_car', 'Commute - car', 3, 'km'],
  ['commute_two_wheeler', 'Commute - two-wheeler', 3, 'km'], ['commute_bus', 'Commute - bus', 3, 'km'],
  ['commute_auto', 'Commute - auto-rickshaw', 3, 'km'], ['commute_train', 'Commute - metro / train', 3, 'km'],
  ['commute_ev', 'Commute - electric two-wheeler', 3, 'km'],
]

function FactorsTab() {
  const invalidate = useInvalidateAll()
  const q = useQuery({ queryKey: ['factors'], queryFn: () => get<Factor[]>('/factors/') })
  const [form, setForm] = useState({ activity: 'electricity_grid', value: '', valid_from: localISODate(), source: '', notes: '' })
  const meta = ACTIVITIES.find((a) => a[0] === form.activity)!
  const add = useMutation({
    mutationFn: () => api.post('/factors/', { ...form, value: Number(form.value), scope: meta[2], activity_unit: meta[3] }),
    onSuccess: () => {
      toast.success('New factor version published')
      setForm({ ...form, value: '', source: '', notes: '' })
      invalidate()
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    add.mutate()
  }
  return (
    <div className="grid cols-3">
      <Card title="Publish a new factor version" subtitle="History is never overwritten: past results stay reproducible, new values apply from their start date.">
        <form className="form" onSubmit={submit}>
          <Field label="Activity">
            <select value={form.activity} onChange={(e) => setForm({ ...form, activity: e.target.value })}>
              {ACTIVITIES.map(([v, l, s]) => <option key={v} value={v}>{l} (Scope {s})</option>)}
            </select>
          </Field>
          <div className="form-row">
            <Field label={`kg CO₂e per ${meta[3]}`}><input type="number" min="0" step="any" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} required /></Field>
            <Field label="Valid from"><input type="date" value={form.valid_from} onChange={(e) => setForm({ ...form, valid_from: e.target.value })} required /></Field>
          </div>
          <Field label="Source / publication"><input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} required placeholder="CEA CO2 Baseline Database v20" /></Field>
          <Field label="Notes"><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field>
          <button className="btn primary" disabled={add.isPending}>Publish version</button>
        </form>
      </Card>
      <Card className="span-2" title="Factor register">
        {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} /> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Activity</th><th>Scope</th><th className="num">kg CO₂e</th><th>Valid from</th><th>Ver.</th><th>Source</th></tr></thead>
              <tbody>
                {q.data?.map((f) => (
                  <tr key={f.id}>
                    <td>{f.activity_label}</td><td>{f.scope}</td><td className="num">{f.value} / {f.activity_unit}</td>
                    <td>{f.valid_from}</td><td>v{f.version}</td><td className="wrap small muted">{f.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

// ------------------------------------------------------------------ buildings

const TYPES: [string, string][] = [['academic', 'Academic block'], ['lab', 'Laboratory'], ['library', 'Library'],
  ['admin', 'Administration'], ['hostel', 'Hostel'], ['canteen', 'Canteen / Food court'], ['sports', 'Sports facility']]

function BuildingsTab() {
  const invalidate = useInvalidateAll()
  const q = useQuery({ queryKey: ['buildings'], queryFn: () => get<Building[]>('/buildings/') })
  const blank = { name: '', code: '', type: 'academic', area_m2: '', occupants: '', latitude: '', longitude: '' }
  const [form, setForm] = useState(blank)
  const add = useMutation({
    mutationFn: () => api.post('/buildings/', {
      ...form, area_m2: Number(form.area_m2), occupants: Number(form.occupants),
      latitude: form.latitude ? Number(form.latitude) : null, longitude: form.longitude ? Number(form.longitude) : null,
    }),
    onSuccess: () => {
      toast.success('Building added – now add its meters')
      setForm(blank)
      invalidate()
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    add.mutate()
  }
  return (
    <div className="grid cols-3">
      <Card title="Add a building" subtitle="Extend monitoring building by building">
        <form className="form" onSubmit={submit}>
          <Field label="Name"><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></Field>
          <div className="form-row">
            <Field label="Code"><input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} required maxLength={20} /></Field>
            <Field label="Type">
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                {TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Field>
          </div>
          <div className="form-row">
            <Field label="Floor area (m²)"><input type="number" min="1" value={form.area_m2} onChange={(e) => setForm({ ...form, area_m2: e.target.value })} required /></Field>
            <Field label="Occupants"><input type="number" min="0" value={form.occupants} onChange={(e) => setForm({ ...form, occupants: e.target.value })} required /></Field>
          </div>
          <div className="form-row">
            <Field label="Latitude"><input type="number" step="any" value={form.latitude} onChange={(e) => setForm({ ...form, latitude: e.target.value })} /></Field>
            <Field label="Longitude"><input type="number" step="any" value={form.longitude} onChange={(e) => setForm({ ...form, longitude: e.target.value })} /></Field>
          </div>
          <button className="btn primary" disabled={add.isPending}>Add building</button>
        </form>
      </Card>
      <Card className="span-2" title="Buildings in the boundary">
        {q.isLoading ? <Loading /> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Code</th><th>Name</th><th>Type</th><th className="num">Area m²</th><th className="num">Occupants</th></tr></thead>
              <tbody>
                {q.data?.map((b) => (
                  <tr key={b.id}><td><b>{b.code}</b></td><td>{b.name}</td><td className="muted">{b.type_label}</td>
                    <td className="num">{num(b.area_m2)}</td><td className="num">{num(b.occupants)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

// ------------------------------------------------------------------ devices

interface Gateway {
  id: number
  name: string
  key: string
  is_active: boolean
  last_seen: string | null
}

function DevicesTab() {
  const invalidate = useInvalidateAll()
  const meters = useQuery({ queryKey: ['meters'], queryFn: () => get<Meter[]>('/meters/'), refetchInterval: 60000 })
  const gateways = useQuery({ queryKey: ['gateways'], queryFn: () => get<Gateway[]>('/gateways/') })
  const buildings = useQuery({ queryKey: ['buildings'], queryFn: () => get<Building[]>('/buildings/') })
  const blank = { name: '', serial: '', kind: 'electricity', building: '', unit: 'kWh', max_value: '0', capacity: '0' }
  const [form, setForm] = useState(blank)
  const add = useMutation({
    mutationFn: () => api.post('/meters/', {
      ...form, building: form.building || null, max_value: Number(form.max_value), capacity: Number(form.capacity),
      gateway: gateways.data?.[0]?.id ?? null,
    }),
    onSuccess: () => {
      toast.success('Meter registered')
      setForm(blank)
      invalidate()
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const toggle = useMutation({
    mutationFn: (m: Meter) => api.patch(`/meters/${m.id}/`, { is_active: !m.is_active }),
    onSuccess: () => invalidate(),
    onError: (e) => toast.error(errorMessage(e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    add.mutate()
  }
  const key = gateways.data?.[0]?.key ?? '<gateway-key>'
  const example = `curl -X POST http://127.0.0.1:8010/api/ingest/ \\
  -H "Content-Type: application/json" -H "X-Gateway-Key: ${key}" \\
  -d '{"readings":[{"serial":"EM-ACA","value":42.5,"interval_minutes":15}]}'`

  return (
    <div className="stack">
      <div className="grid cols-3">
        <Card title="Edge gateways" subtitle="Devices authenticate with the gateway key">
          {gateways.data?.map((g) => (
            <div key={g.id} className="list-item">
              <span className={`dot ${g.last_seen && Date.now() - new Date(g.last_seen).getTime() < 7200000 ? 'on' : 'off'}`} style={{ marginTop: 6 }} />
              <div style={{ minWidth: 0 }}>
                <b>{g.name}</b>
                <div className="small muted">Last seen {timeAgo(g.last_seen)}</div>
                <code className="small" style={{ wordBreak: 'break-all' }}>{g.key}</code>
              </div>
            </div>
          ))}
        </Card>
        <Card className="span-2" title="Device ingestion API" subtitle="ESP32 boards, Modbus/LoRaWAN gateways or scripts POST readings here (value = consumption in the interval).">
          <pre className="small" style={{ background: '#10281c', color: '#d7eadf', padding: 12, borderRadius: 8, overflowX: 'auto', margin: 0 }}>{example}</pre>
          <p className="small muted">Out-of-range values are stored but flagged as suspect and excluded from totals, never silently corrected.</p>
        </Card>
      </div>
      <div className="grid cols-3">
        <Card title="Register a meter">
          <form className="form" onSubmit={submit}>
            <Field label="Name"><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></Field>
            <div className="form-row">
              <Field label="Serial"><input value={form.serial} onChange={(e) => setForm({ ...form, serial: e.target.value })} required /></Field>
              <Field label="Kind">
                <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value, unit: e.target.value.startsWith('water') ? 'kL' : 'kWh' })}>
                  <option value="electricity">Grid electricity</option><option value="solar">Solar generation</option>
                  <option value="water">Water consumption</option>
                </select>
              </Field>
            </div>
            <Field label="Building">
              <select value={form.building} onChange={(e) => setForm({ ...form, building: e.target.value })} required>
                <option value="">Select…</option>
                {buildings.data?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </Field>
            <div className="form-row">
              <Field label={`Max per hour (${form.unit})`}><input type="number" min="0" value={form.max_value} onChange={(e) => setForm({ ...form, max_value: e.target.value })} /></Field>
              {form.kind === 'solar' && <Field label="Capacity kWp"><input type="number" min="0" value={form.capacity} onChange={(e) => setForm({ ...form, capacity: e.target.value })} /></Field>}
            </div>
            <button className="btn primary" disabled={add.isPending}>Register meter</button>
          </form>
        </Card>
        <Card className="span-2" title="Meters">
          {meters.isLoading ? <Loading /> : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Status</th><th>Serial</th><th>Name</th><th>Kind</th><th>Last reading</th><th></th></tr></thead>
                <tbody>
                  {meters.data?.map((m) => (
                    <tr key={m.id}>
                      <td><span className={`dot ${m.online ? 'on' : 'off'}`} /> {m.is_active ? (m.online ? 'online' : 'offline') : 'disabled'}</td>
                      <td><code>{m.serial}</code></td><td>{m.name}</td><td className="muted">{m.kind_label}</td>
                      <td>{dateTime(m.last_reading_at)}</td>
                      <td><button className="btn sm" onClick={() => toggle.mutate(m)}>{m.is_active ? 'Disable' : 'Enable'}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ data quality

interface Quality {
  meters: { id: number; meter: string; serial: string; kind: string; building: string; reporting: boolean; last_reading_at: string | null; completeness_pct: number }[]
  totals: { reporting_pct: number; completeness_pct: number; suspect_readings_7d: number; mean_hours_to_resolve: number | null; latest_reading: string | null }
}

function QualityTab() {
  const q = useQuery({ queryKey: ['quality'], queryFn: () => get<Quality>('/analytics/data-quality/') })
  if (q.isLoading) return <Loading />
  if (q.isError || !q.data) return <ErrorState error={q.error} retry={q.refetch} />
  return (
    <>
      <div className="grid kpis">
        <Stat label="Meters reporting" value={num(q.data.totals.reporting_pct, 0)} unit="%" />
        <Stat label="Data completeness (7 days)" value={num(q.data.totals.completeness_pct, 1)} unit="%" />
        <Stat label="Suspect readings (7 days)" value={q.data.totals.suspect_readings_7d} sub="Flagged, excluded from totals" />
        <Stat label="Mean time to resolve alerts" value={q.data.totals.mean_hours_to_resolve === null ? '–' : num(q.data.totals.mean_hours_to_resolve, 1)} unit="h" />
        <Stat label="Latest reading" value={timeAgo(q.data.totals.latest_reading)} />
      </div>
      <Card title="Per-meter completeness" subtitle="Share of hours in the last 7 days with at least one reading">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Meter</th><th>Building</th><th>Kind</th><th>Status</th><th className="num">Completeness</th><th>Last reading</th></tr></thead>
            <tbody>
              {q.data.meters.map((m) => (
                <tr key={m.id}>
                  <td>{m.meter}<div className="small muted">{m.serial}</div></td><td>{m.building}</td><td className="muted">{m.kind}</td>
                  <td>{m.reporting ? <Badge kind="ok">reporting</Badge> : <Badge kind="high">silent</Badge>}</td>
                  <td className="num">{num(m.completeness_pct, 1)}%</td><td>{dateTime(m.last_reading_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}

// ------------------------------------------------------------------ users

interface UserRow extends User {
  is_active: boolean
  last_login: string | null
}

function UsersTab() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['users'], queryFn: () => get<UserRow[]>('/users/') })
  const update = useMutation({
    mutationFn: ({ id, ...body }: Partial<UserRow> & { id: number }) => api.patch(`/users/${id}/`, body),
    onSuccess: () => {
      toast.success('User updated')
      qc.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  return (
    <Card title="Users & roles" subtitle="Administrators manage settings; facility staff handle alerts and logs; students and staff use the community portal.">
      {q.isLoading ? <Loading /> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Username</th><th>Name</th><th>Department</th><th>Role</th><th>Last login</th><th>Active</th></tr></thead>
            <tbody>
              {q.data?.map((u) => (
                <tr key={u.id}>
                  <td><b>{u.username}</b></td><td>{u.first_name} {u.last_name}</td><td className="muted">{u.department || '–'}</td>
                  <td>
                    <select value={u.role} onChange={(e) => update.mutate({ id: u.id, role: e.target.value as User['role'] })} style={{ width: 'auto' }}>
                      <option value="admin">Administrator</option><option value="facility">Facility team</option><option value="community">Student / Staff</option>
                    </select>
                  </td>
                  <td>{dateTime(u.last_login)}</td>
                  <td><input type="checkbox" checked={u.is_active} style={{ width: 'auto' }} onChange={() => update.mutate({ id: u.id, is_active: !u.is_active })} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
