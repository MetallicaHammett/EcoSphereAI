import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Bar, BarChart, CartesianGrid, Cell, Tooltip, XAxis, YAxis } from 'recharts'
import { Bike, Bus, Fuel } from 'lucide-react'
import { api, errorMessage, get } from '../api'
import { isOperator, periodParams, useAuth, usePeriod } from '../store'
import type { TransportData } from '../types'
import { Card, ErrorState, Field, Loading, PageHeader, PeriodPicker, Stat } from '../components/ui'
import { axis, ChartBox, COLORS, gridProps, tooltipStyle } from '../components/charts'
import { localISODate, num } from '../format'

export default function Transport() {
  const period = usePeriod((s) => s.period)
  const user = useAuth((s) => s.user)
  const q = useQuery({ queryKey: ['transport', period], queryFn: () => get<TransportData>('/analytics/transport/', periodParams(period)) })

  return (
    <>
      <PageHeader title="Transport & mobility"
        subtitle="Campus fleet fuel logs plus anonymous commute surveys give Scope 1 fleet and Scope 3 commuting emissions by mode."
        actions={<PeriodPicker />} />
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} retry={q.refetch} /> : q.data && (
        <>
          <div className="grid kpis">
            <Stat icon={<Fuel size={14} />} label="Fleet fuel" value={num(q.data.totals.fleet_litres)} unit="L"
              sub={`${num(q.data.totals.fleet_km)} km driven`} />
            <Stat icon={<Bus size={14} />} label="Fleet emissions" value={num(q.data.totals.fleet_tco2e, 1)} unit="tCO₂e" sub="Scope 1" />
            <Stat label="Commuting (annual)" value={num(q.data.totals.commute_annual_tco2e)} unit="tCO₂e/yr" sub="Scope 3, survey-based" />
            <Stat icon={<Bike size={14} />} label="Sustainable commutes" value={num(q.data.totals.sustainable_share_pct, 0)} unit="%"
              sub="Walk, cycle, bus, metro, EV" />
            <Stat label="Survey responses" value={num(q.data.totals.survey_responses)} sub={`Avg ${q.data.totals.average_distance_km} km one way`} />
          </div>
          <div className="grid cols-2">
            <Card title="How people get to campus" subtitle="Share of survey responses · green = sustainable mode">
              <ChartBox>
                <BarChart data={q.data.modes} layout="vertical" margin={{ left: 10 }}>
                  <CartesianGrid {...gridProps} horizontal={false} vertical />
                  <XAxis type="number" tick={axis} unit="%" />
                  <YAxis type="category" dataKey="label" tick={axis} width={150} />
                  <Tooltip {...tooltipStyle} formatter={(v) => `${num(Number(v), 1)}%`} />
                  <Bar dataKey="share_pct" name="Share" radius={[0, 4, 4, 0]}>
                    {q.data.modes.map((m) => <Cell key={m.mode} fill={m.sustainable ? COLORS.primary : COLORS.scope1} />)}
                  </Bar>
                </BarChart>
              </ChartBox>
            </Card>
            <Card title="Commuting emissions by mode" subtitle="tCO₂e per year scaled to the campus population">
              <ChartBox>
                <BarChart data={q.data.modes} layout="vertical" margin={{ left: 10 }}>
                  <CartesianGrid {...gridProps} horizontal={false} vertical />
                  <XAxis type="number" tick={axis} />
                  <YAxis type="category" dataKey="label" tick={axis} width={150} />
                  <Tooltip {...tooltipStyle} formatter={(v) => `${num(Number(v), 1)} t/yr`} />
                  <Bar dataKey="annual_tco2e" name="tCO₂e/yr" fill={COLORS.scope3} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ChartBox>
            </Card>
          </div>
          <div className="grid cols-3 mt">
            <Card className="span-2" title="Campus fleet" subtitle="Fuel efficiency by vehicle this period">
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Vehicle</th><th>Fuel</th><th className="num">Litres</th><th className="num">km</th><th className="num">km/L</th><th className="num">tCO₂e</th></tr></thead>
                  <tbody>
                    {q.data.fleet.map((v) => (
                      <tr key={v.asset + v.fuel}>
                        <td>{v.asset}</td><td className="muted">{v.fuel}</td><td className="num">{num(v.litres)}</td>
                        <td className="num">{num(v.km)}</td><td className="num">{num(v.km_per_litre, 2)}</td><td className="num">{num(v.tco2e, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
            <div className="stack">
              {isOperator(user) && <FuelForm />}
              <Card title="Your commute footprint">
                <p className="small muted" style={{ marginTop: 0 }}>Add your own commute anonymously to improve the campus estimate.</p>
                <Link className="btn primary" to="/community">Open commute calculator</Link>
              </Card>
            </div>
          </div>
        </>
      )}
    </>
  )
}

const FUEL_CATEGORIES = [['fleet', 'Campus fleet', 'diesel'], ['generator', 'Diesel generator', 'diesel'],
  ['canteen', 'Canteen & labs (LPG)', 'lpg'], ['refrigerant', 'Refrigerant top-up', 'refrigerant_r410a']] as const
const FUELS: Record<string, [string, string][]> = {
  fleet: [['diesel', 'Diesel (L)'], ['petrol', 'Petrol (L)']],
  generator: [['diesel', 'Diesel (L)']],
  canteen: [['lpg', 'LPG (kg)']],
  refrigerant: [['refrigerant_r410a', 'R-410A (kg)'], ['refrigerant_r32', 'R-32 (kg)'], ['refrigerant_r22', 'R-22 (kg)']],
}

function FuelForm() {
  const qc = useQueryClient()
  const today = localISODate()
  const [form, setForm] = useState({ date: today, category: 'fleet', activity: 'diesel', quantity: '', asset: '', distance_km: '' })
  const save = useMutation({
    mutationFn: () => api.post('/fuel-logs/', {
      ...form, quantity: Number(form.quantity), distance_km: form.distance_km ? Number(form.distance_km) : null,
    }),
    onSuccess: () => {
      toast.success('Fuel entry saved')
      setForm({ ...form, quantity: '', distance_km: '' })
      qc.invalidateQueries({ queryKey: ['transport'] })
      qc.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <Card title="Log fuel (Scope 1)">
      <form className="form" onSubmit={submit}>
        <div className="form-row">
          <Field label="Date"><input type="date" value={form.date} max={today} onChange={(e) => setForm({ ...form, date: e.target.value })} required /></Field>
          <Field label="Source">
            <select value={form.category} onChange={(e) => {
              const cat = FUEL_CATEGORIES.find((c) => c[0] === e.target.value)!
              setForm({ ...form, category: cat[0], activity: cat[2] })
            }}>
              {FUEL_CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
        </div>
        <div className="form-row">
          <Field label="Fuel">
            <select value={form.activity} onChange={(e) => setForm({ ...form, activity: e.target.value })}>
              {FUELS[form.category].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
          <Field label="Quantity"><input type="number" min="0.1" step="0.1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required /></Field>
        </div>
        <div className="form-row">
          <Field label="Vehicle / asset"><input value={form.asset} onChange={(e) => setForm({ ...form, asset: e.target.value })} placeholder="TN-09-BX-1101" /></Field>
          {form.category === 'fleet' && (
            <Field label="Distance (km)"><input type="number" min="0" step="0.1" value={form.distance_km} onChange={(e) => setForm({ ...form, distance_km: e.target.value })} /></Field>
          )}
        </div>
        <button className="btn primary" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save entry'}</button>
      </form>
    </Card>
  )
}
