import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Award, Lightbulb, TrendingDown, TrendingUp } from 'lucide-react'
import { api, errorMessage, get } from '../api'
import type { Footprint, LeaderRow } from '../types'
import { Card, ErrorState, Field, Loading, PageHeader } from '../components/ui'
import { num, shortDate } from '../format'

const MODES: [string, string][] = [
  ['walk', 'Walking'], ['cycle', 'Cycling'], ['bus', 'Bus / campus shuttle'], ['train', 'Metro / train'],
  ['ev', 'Electric two-wheeler'], ['two_wheeler', 'Petrol two-wheeler'], ['auto', 'Auto-rickshaw'], ['car', 'Car'],
]

const TIPS = [
  'Switch off lights, fans and projectors when you are the last to leave a room.',
  'Set room AC to 24–26 °C: every degree warmer saves about 6% of cooling energy.',
  'Report dripping taps and running cisterns from the community portal – a dripping tap wastes 30+ litres a day.',
  'Carry a refillable bottle and lunch box; segregate wet and dry waste at the bins.',
  'Use the stairs for one or two floors and the campus shuttle or metro for your commute.',
  'Unplug chargers and enable sleep mode on lab and hostel computers.',
]

interface Leaderboard {
  hostels: LeaderRow[]
  departments: LeaderRow[]
  period: { this_week_start: string; baseline_start: string }
}

interface Commute {
  id: number
  mode_label: string
  distance_km: number
  days_per_week: number
  created_at: string
}

export default function Community() {
  const board = useQuery({ queryKey: ['leaderboard'], queryFn: () => get<Leaderboard>('/analytics/leaderboard/') })
  return (
    <>
      <PageHeader title="Community portal"
        subtitle="Behaviour change is a major lever. Inter-hostel energy-saving competition, your personal commute footprint and everyday tips." />
      <div className="grid cols-2">
        <Card title="Inter-hostel energy challenge" subtitle={board.data ? `Electricity per resident this week vs the previous four weeks (since ${shortDate(board.data.period.this_week_start)})` : undefined}>
          {board.isLoading ? <Loading /> : board.isError ? <ErrorState error={board.error} /> : <Board rows={board.data!.hostels} unit="resident" />}
        </Card>
        <Card title="Department & building challenge" subtitle="Academic blocks, labs and library">
          {board.isLoading ? <Loading /> : board.isError ? <ErrorState error={board.error} /> : <Board rows={board.data!.departments} unit="occupant" />}
        </Card>
      </div>
      <div className="grid cols-3 mt">
        <CommuteCalculator />
        <Card title="Everyday tips" subtitle="Small actions, campus-wide impact">
          <div className="list">
            {TIPS.map((t) => (
              <div className="list-item small" key={t}><Lightbulb size={16} color="var(--warn)" style={{ flex: 'none' }} />{t}</div>
            ))}
          </div>
        </Card>
      </div>
    </>
  )
}

function Board({ rows, unit }: { rows: LeaderRow[]; unit: string }) {
  const medal = ['gold', 'silver', 'bronze']
  return (
    <div className="list">
      {rows.map((r, i) => (
        <div className="list-item" key={r.id} style={{ alignItems: 'center' }}>
          <span className={`rank ${medal[i] ?? ''}`}>{r.rank}</span>
          <div style={{ flex: 1 }}>
            <b>{r.building}</b>
            <div className="small muted">{num(r.kwh_per_occupant_day, 2)} kWh per {unit} per day (was {num(r.previous, 2)})</div>
          </div>
          <span className="row small" style={{ color: r.change_pct <= 0 ? 'var(--primary)' : 'var(--danger)', gap: 4 }}>
            {r.change_pct <= 0 ? <TrendingDown size={15} /> : <TrendingUp size={15} />}
            {r.change_pct > 0 ? '+' : ''}{num(r.change_pct, 1)}%
          </span>
          <span className="badge ok"><Award size={12} /> {r.points} pts</span>
        </div>
      ))}
    </div>
  )
}

function CommuteCalculator() {
  const qc = useQueryClient()
  const [form, setForm] = useState({ mode: 'bus', distance_km: '8', days_per_week: '5', respondent: 'student' })
  const [result, setResult] = useState<Footprint | null>(null)
  const mine = useQuery({ queryKey: ['my-commutes'], queryFn: () => get<Commute[]>('/commute/') })
  const save = useMutation({
    mutationFn: async () => (await api.post<{ footprint: Footprint }>('/commute/', {
      ...form, distance_km: Number(form.distance_km), days_per_week: Number(form.days_per_week),
    })).data,
    onSuccess: (data) => {
      setResult(data.footprint)
      toast.success('Thanks! Your response was added anonymously to the campus estimate.')
      qc.invalidateQueries({ queryKey: ['my-commutes'] })
      qc.invalidateQueries({ queryKey: ['transport'] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <Card className="span-2" title="My commute footprint" subtitle="Personal answers are private; only campus-wide totals are reported.">
      <div className="grid cols-2">
        <form className="form" onSubmit={submit}>
          <Field label="How do you usually travel to campus?">
            <select value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}>
              {MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </Field>
          <div className="form-row">
            <Field label="One-way distance (km)">
              <input type="number" min="0" max="200" step="0.1" value={form.distance_km} onChange={(e) => setForm({ ...form, distance_km: e.target.value })} required />
            </Field>
            <Field label="Days per week">
              <input type="number" min="1" max="7" value={form.days_per_week} onChange={(e) => setForm({ ...form, days_per_week: e.target.value })} required />
            </Field>
          </div>
          <Field label="I am a">
            <select value={form.respondent} onChange={(e) => setForm({ ...form, respondent: e.target.value })}>
              <option value="student">Student</option><option value="staff">Staff member</option>
            </select>
          </Field>
          <button className="btn primary" disabled={save.isPending}>{save.isPending ? 'Calculating…' : 'Calculate & submit'}</button>
        </form>
        <div>
          {result ? (
            <div className="stack">
              <div>
                <div className="stat-label">Your commute emits about</div>
                <div className="stat-value">{num(result.annual_kg)}<small>kg CO₂e / year</small></div>
                <div className="small muted">{num(result.annual_km)} km a year over a 44-week academic year</div>
              </div>
              <div className="list small">
                <div className="list-item">Per trip: <b>{num(result.per_trip_kg, 2)} kg</b></div>
                <div className="list-item">Saving vs driving alone: <b>{num(result.saving_vs_car_kg)} kg/yr</b></div>
                <div className="list-item">Trees needed to absorb it: <b>{num(result.trees_to_offset, 1)}</b></div>
              </div>
              <div className="notice">{result.tip}</div>
            </div>
          ) : (
            <div className="state small">Submit your usual commute to see your annual footprint and how it compares.</div>
          )}
          {!!mine.data?.length && (
            <p className="small muted">You have submitted {mine.data.length} response(s); latest: {mine.data[0].mode_label}, {mine.data[0].distance_km} km.</p>
          )}
        </div>
      </div>
    </Card>
  )
}
