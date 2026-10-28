import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, Tooltip, XAxis, YAxis } from 'recharts'
import { Leaf, Recycle, Trash2 } from 'lucide-react'
import { api, errorMessage, get } from '../api'
import { isOperator, periodParams, useAuth, usePeriod } from '../store'
import type { Building, WasteData } from '../types'
import { Card, ErrorState, Field, Loading, PageHeader, PeriodPicker, Stat } from '../components/ui'
import { axis, ChartBox, gridProps, tooltipStyle } from '../components/charts'
import { compact, localISODate, num, shortDate } from '../format'

const CAT_COLORS: Record<string, string> = {
  wet: '#1f7a4d', dry: '#9aa9a1', recyclable: '#3b82c4', ewaste: '#8b6cc1', hazardous: '#c2410c',
}
const DISP_COLORS: Record<string, string> = {
  composted: '#1f7a4d', biogas: '#7a8b2f', recycled: '#3b82c4', landfill: '#9aa9a1', incinerated: '#c2410c',
}
const CATEGORIES = [['wet', 'Wet / organic'], ['dry', 'Dry'], ['recyclable', 'Recyclable'], ['ewaste', 'E-waste'], ['hazardous', 'Hazardous']]
const DISPOSALS = [['composted', 'Composted'], ['biogas', 'Biogas'], ['recycled', 'Recycled'], ['landfill', 'Landfill'], ['incinerated', 'Incinerated (authorised)']]

interface WasteLog {
  id: number
  date: string
  building_name: string | null
  category_label: string
  disposal_label: string
  weight_kg: number
  notes: string
}

export default function Waste() {
  const period = usePeriod((s) => s.period)
  const user = useAuth((s) => s.user)
  const q = useQuery({ queryKey: ['waste', period], queryFn: () => get<WasteData>('/analytics/waste/', periodParams(period)) })
  const logs = useQuery({ queryKey: ['waste-logs'], queryFn: () => get<WasteLog[]>('/waste-logs/', { limit: 40 }) })

  return (
    <>
      <PageHeader title="Waste management"
        subtitle="Waste measured by stream. Diversion rate (share recycled, composted or turned into biogas) is the headline indicator."
        actions={<PeriodPicker />} />
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} retry={q.refetch} /> : q.data && (
        <>
          <div className="grid kpis">
            <Stat icon={<Trash2 size={14} />} label="Waste generated" value={num(q.data.totals.total_kg / 1000, 1)} unit="tonnes"
              sub={`${num(q.data.totals.per_person_day_kg, 3)} kg per person per day`} />
            <Stat icon={<Recycle size={14} />} label="Diversion rate" value={num(q.data.totals.diversion_rate_pct, 1)} unit="%" />
            <Stat icon={<Leaf size={14} />} label="Organic composted / biogas" value={num(q.data.totals.organic_treated_pct, 0)} unit="%" />
            <Stat label="Avoided emissions" value={num(q.data.totals.avoided_tco2e, 2)} unit="tCO₂e"
              sub={`vs landfill · ${num(q.data.totals.emitted_tco2e, 2)} t emitted`} />
            <Stat label="E-waste / hazardous" value={`${num(q.data.totals.ewaste_kg)} / ${num(q.data.totals.hazardous_kg)}`} unit="kg"
              sub="Logged for compliance" />
          </div>
          <div className="grid cols-3">
            <Card className="span-2" title="Weekly waste by stream" subtitle="kg per week">
              <ChartBox>
                <BarChart data={q.data.weekly}>
                  <CartesianGrid {...gridProps} />
                  <XAxis dataKey="week" tick={axis} tickFormatter={shortDate} />
                  <YAxis tick={axis} tickFormatter={compact} width={44} />
                  <Tooltip {...tooltipStyle} labelFormatter={(l) => `Week of ${shortDate(String(l))}`} formatter={(v) => `${num(Number(v))} kg`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {CATEGORIES.map(([k, label]) => <Bar key={k} dataKey={k} name={label} stackId="w" fill={CAT_COLORS[k]} />)}
                </BarChart>
              </ChartBox>
            </Card>
            <Card title="Where it goes" subtitle="Disposal route">
              <ChartBox>
                <PieChart>
                  <Pie data={q.data.by_disposal} dataKey="kg" nameKey="disposal" innerRadius={50} outerRadius={90} paddingAngle={2}>
                    {q.data.by_disposal.map((d) => <Cell key={d.key} fill={DISP_COLORS[d.key]} />)}
                  </Pie>
                  <Tooltip {...tooltipStyle} formatter={(v) => `${num(Number(v))} kg`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ChartBox>
            </Card>
          </div>
        </>
      )}
      <div className={`grid mt ${isOperator(user) ? 'cols-3' : ''}`}>
        {isOperator(user) && <WasteForm />}
        <Card className={isOperator(user) ? 'span-2' : ''} title="Recent weighings">
          {logs.isLoading ? <Loading /> : logs.isError ? <ErrorState error={logs.error} /> : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Date</th><th>Stream</th><th>Disposal</th><th>Source</th><th className="num">kg</th></tr></thead>
                <tbody>
                  {logs.data?.map((l) => (
                    <tr key={l.id}>
                      <td>{shortDate(l.date)}</td><td>{l.category_label}</td><td>{l.disposal_label}</td>
                      <td className="muted">{l.building_name ?? 'Campus collection'}</td><td className="num">{num(l.weight_kg, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  )
}

function WasteForm() {
  const qc = useQueryClient()
  const buildings = useQuery({ queryKey: ['buildings'], queryFn: () => get<Building[]>('/buildings/') })
  const today = localISODate()
  const [form, setForm] = useState({ date: today, category: 'wet', disposal: 'composted', weight_kg: '', building: '', notes: '' })
  const save = useMutation({
    mutationFn: () => api.post('/waste-logs/', { ...form, building: form.building || null, weight_kg: Number(form.weight_kg) }),
    onSuccess: () => {
      toast.success('Weighing recorded')
      setForm({ ...form, weight_kg: '', notes: '' })
      qc.invalidateQueries({ queryKey: ['waste'] })
      qc.invalidateQueries({ queryKey: ['waste-logs'] })
      qc.invalidateQueries({ queryKey: ['overview'] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <Card title="Record a weighing" subtitle="From collection-point scales">
      <form className="form" onSubmit={submit}>
        <Field label="Date"><input type="date" value={form.date} max={today} onChange={(e) => setForm({ ...form, date: e.target.value })} required /></Field>
        <div className="form-row">
          <Field label="Stream">
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              {CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
          <Field label="Disposal">
            <select value={form.disposal} onChange={(e) => setForm({ ...form, disposal: e.target.value })}>
              {DISPOSALS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Weight (kg)"><input type="number" min="0.1" step="0.1" value={form.weight_kg} onChange={(e) => setForm({ ...form, weight_kg: e.target.value })} required /></Field>
        <Field label="Source building (optional)">
          <select value={form.building} onChange={(e) => setForm({ ...form, building: e.target.value })}>
            <option value="">Campus collection</option>
            {buildings.data?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </Field>
        <button className="btn primary" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save weighing'}</button>
      </form>
    </Card>
  )
}
