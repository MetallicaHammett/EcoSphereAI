import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { CircleMarker, MapContainer, TileLayer, Tooltip as MapTip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { CheckCircle2, CloudSun, Eye, Radar, Radio, Wind } from 'lucide-react'
import { api, errorMessage, get } from '../api'
import { isOperator, useAuth } from '../store'
import type { AlertItem, LiveData } from '../types'
import { Badge, Card, Empty, ErrorState, Loading, PageHeader, Segmented, Stat } from '../components/ui'
import { dateTime, inr, num, timeAgo } from '../format'

type StatusFilter = 'open' | 'acknowledged' | 'resolved' | 'all'

export default function Operations() {
  const user = useAuth((s) => s.user)
  const qc = useQueryClient()
  const live = useQuery({ queryKey: ['live'], queryFn: () => get<LiveData>('/analytics/live/'), refetchInterval: 30000 })
  const scan = useMutation({
    mutationFn: () => api.post<{ created: number }>('/analytics/anomalies/scan/'),
    onSuccess: ({ data }) => {
      toast.success(data.created ? `${data.created} new alert(s) raised` : 'Scan complete – no new anomalies')
      qc.invalidateQueries({ queryKey: ['alerts'] })
      qc.invalidateQueries({ queryKey: ['alert-count'] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  return (
    <>
      <PageHeader
        title="Operations console"
        subtitle="Live building status, IoT health and anomaly alerts that double as work orders for the facility team."
        actions={isOperator(user) && (
          <button className="btn primary" onClick={() => scan.mutate()} disabled={scan.isPending}>
            <Radar size={15} /> {scan.isPending ? 'Scanning…' : 'Run anomaly scan'}
          </button>
        )}
      />
      {live.isLoading ? <Loading /> : live.isError ? <ErrorState error={live.error} retry={live.refetch} /> : live.data && <LivePanel d={live.data} />}
      <AlertsPanel canEdit={isOperator(user)} />
    </>
  )
}

function LivePanel({ d }: { d: LiveData }) {
  const stale = !d.updated_at || Date.now() - new Date(d.updated_at).getTime() > 2 * 3600 * 1000
  const mapped = d.buildings.filter((b) => b.latitude !== null && b.longitude !== null)
  const center: [number, number] = mapped.length
    ? [mapped.reduce((s, b) => s + b.latitude!, 0) / mapped.length, mapped.reduce((s, b) => s + b.longitude!, 0) / mapped.length]
    : [13.0518, 80.2125]
  const maxKw = Math.max(...d.buildings.map((b) => b.grid_kw + b.solar_kw), 1)

  return (
    <>
      {stale && (
        <div className="notice warn" style={{ marginBottom: 16 }}>
          No live readings in the last 2 hours (latest {timeAgo(d.updated_at)}). Start the IoT simulator with
          <code> python manage.py simulate </code> or connect real gateways to the ingestion API.
        </div>
      )}
      <div className="grid kpis">
        <Stat icon={<Radio size={14} />} label="Grid demand now" value={num(d.totals.grid_kw)} unit="kW" sub={`Updated ${timeAgo(d.updated_at)}`} />
        <Stat icon={<CloudSun size={14} />} label="Solar generation" value={num(d.totals.solar_kw)} unit="kW"
          sub={d.weather ? `Irradiance ${num(d.weather.irradiance)} W/m²` : undefined} />
        <Stat icon={<Wind size={14} />} label="Water flow" value={num(d.totals.water_klph, 1)} unit="kL/h" />
        <Stat label="Outdoor" value={d.weather ? num(d.weather.temperature, 1) : '–'} unit="°C"
          sub={d.weather ? `${num(d.weather.humidity)}% RH${d.weather.rainfall_mm ? ' · raining' : ''}` : undefined} />
        <Stat label="Meters reporting" value={`${d.meters.online}/${d.meters.total}`}
          sub={d.meters.online === d.meters.total ? 'All devices online' : 'Some devices offline'} />
      </div>
      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        <Card className="span-2" title="Building status" subtitle="Latest reading from each building's meters and indoor sensors">
          <div className="tile-grid">
            {d.buildings.map((b) => (
              <div className="tile" key={b.id}>
                <h3>
                  <span className={`dot ${b.open_alerts ? 'off' : 'on'}`} /> {b.building}
                </h3>
                <div className="small muted">{b.type_label}</div>
                <dl>
                  <dt>Grid</dt><dd>{num(b.grid_kw)} kW</dd>
                  {b.solar_kw > 0 && <><dt>Solar</dt><dd>{num(b.solar_kw)} kW</dd></>}
                  <dt>Water</dt><dd>{num(b.water_klph, 2)} kL/h</dd>
                  {b.temperature !== null && <><dt>Indoor</dt><dd>{b.temperature} °C · {b.humidity}%</dd></>}
                  {b.co2_ppm !== null && <><dt>CO₂</dt><dd style={{ color: b.co2_ppm > 1000 ? 'var(--danger)' : undefined }}>{num(b.co2_ppm)} ppm</dd></>}
                  {b.occupancy !== null && <><dt>Occupancy</dt><dd>{num(b.occupancy)}</dd></>}
                  {b.open_alerts > 0 && <><dt>Alerts</dt><dd style={{ color: 'var(--danger)' }}>{b.open_alerts} open</dd></>}
                </dl>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Campus map" subtitle="Circle size = current load; red = open alerts">
          <div className="map">
            <MapContainer center={center} zoom={17} scrollWheelZoom={false} style={{ height: '100%', width: '100%' }}>
              <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              {mapped.map((b) => (
                <CircleMarker key={b.id} center={[b.latitude!, b.longitude!]} radius={8 + 18 * ((b.grid_kw + b.solar_kw) / maxKw)}
                  pathOptions={{ color: b.open_alerts ? '#c2410c' : '#1f7a4d', fillOpacity: 0.45, weight: 2 }}>
                  <MapTip>
                    <b>{b.building}</b><br />{num(b.grid_kw)} kW grid · {num(b.water_klph, 2)} kL/h
                    {b.open_alerts ? <><br />{b.open_alerts} open alert(s)</> : null}
                  </MapTip>
                </CircleMarker>
              ))}
            </MapContainer>
          </div>
        </Card>
      </div>
    </>
  )
}

function AlertsPanel({ canEdit }: { canEdit: boolean }) {
  const [status, setStatus] = useState<StatusFilter>('open')
  const [category, setCategory] = useState('')
  const q = useQuery({
    queryKey: ['alerts', status, category],
    queryFn: () => get<AlertItem[]>('/alerts/', { ...(status !== 'all' && { status }), ...(category && { category }) }),
  })

  return (
    <Card title="Alerts & work orders" subtitle="Raised automatically by the anomaly detector; acknowledge, add notes and resolve."
      actions={
        <div className="row">
          <select value={category} onChange={(e) => setCategory(e.target.value)} style={{ width: 'auto' }}>
            <option value="">All categories</option>
            <option value="energy">Energy</option>
            <option value="water">Water</option>
            <option value="environment">Indoor environment</option>
            <option value="data_quality">Data quality</option>
          </select>
          <Segmented value={status} onChange={setStatus}
            options={[['open', 'Open'], ['acknowledged', 'In progress'], ['resolved', 'Resolved'], ['all', 'All']]} />
        </div>
      }>
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} retry={q.refetch} /> :
        !q.data?.length ? <Empty><CheckCircle2 size={28} color="var(--primary)" />No alerts here.</Empty> : (
          <div className="stack">
            {q.data.map((a) => <AlertRow key={a.id} a={a} canEdit={canEdit} />)}
          </div>
        )}
    </Card>
  )
}

function AlertRow({ a, canEdit }: { a: AlertItem; canEdit: boolean }) {
  const qc = useQueryClient()
  const user = useAuth((s) => s.user)
  const [notes, setNotes] = useState(a.notes)
  const [editing, setEditing] = useState(false)
  const update = useMutation({
    mutationFn: (body: Partial<AlertItem>) => api.patch(`/alerts/${a.id}/`, body),
    onSuccess: () => {
      toast.success('Alert updated')
      setEditing(false)
      qc.invalidateQueries({ queryKey: ['alerts'] })
      qc.invalidateQueries({ queryKey: ['alert-count'] })
      qc.invalidateQueries({ queryKey: ['live'] })
      qc.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  return (
    <div className={`alert-card ${a.severity}`}>
      <div className="row">
        <Badge kind={a.severity}>{a.severity}</Badge>
        <Badge kind={a.status}>{a.status === 'acknowledged' ? 'in progress' : a.status}</Badge>
        <span className="small muted">{a.category.replace('_', ' ')} · {a.occurred_on}</span>
        <span className="spacer" />
        {a.estimated_cost > 0 && <span className="small"><b>{inr(a.estimated_cost)}</b> <span className="muted">est. waste/day</span></span>}
      </div>
      <h3 style={{ marginTop: 8 }}>{a.title}</h3>
      <p>{a.message}</p>
      <div className="small muted">
        Raised {dateTime(a.created_at)}
        {a.assigned_to_name && ` · assigned to ${a.assigned_to_name}`}
        {a.resolved_at && ` · resolved ${dateTime(a.resolved_at)}`}
      </div>
      {a.notes && !editing && <p className="small"><b>Notes:</b> {a.notes}</p>}
      {canEdit && (
        <div className="row" style={{ marginTop: 10 }}>
          {editing ? (
            <>
              <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Action taken, findings…" style={{ flex: 1, minWidth: 200 }} />
              <button className="btn sm primary" disabled={update.isPending} onClick={() => update.mutate({ notes })}>Save note</button>
              <button className="btn sm" onClick={() => setEditing(false)}>Cancel</button>
            </>
          ) : (
            <>
              {a.status === 'open' && (
                <button className="btn sm" disabled={update.isPending}
                  onClick={() => update.mutate({ status: 'acknowledged', assigned_to: user?.id ?? null })}>
                  <Eye size={13} /> Acknowledge
                </button>
              )}
              {a.status !== 'resolved' ? (
                <button className="btn sm primary" disabled={update.isPending} onClick={() => update.mutate({ status: 'resolved' })}>
                  <CheckCircle2 size={13} /> Resolve
                </button>
              ) : (
                <button className="btn sm" disabled={update.isPending} onClick={() => update.mutate({ status: 'open' })}>Reopen</button>
              )}
              <button className="btn sm" onClick={() => setEditing(true)}>Add note</button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
