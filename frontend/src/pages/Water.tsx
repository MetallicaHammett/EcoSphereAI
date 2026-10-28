import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, Tooltip, XAxis, YAxis } from 'recharts'
import { CloudRain, Droplets, IndianRupee, Recycle } from 'lucide-react'
import { get } from '../api'
import { periodParams, usePeriod } from '../store'
import type { WaterData } from '../types'
import { Badge, Card, ErrorState, Loading, PageHeader, PeriodPicker, Stat } from '../components/ui'
import { axis, ChartBox, gridProps, tooltipStyle } from '../components/charts'
import { compact, inr, num, shortDate } from '../format'

const SOURCE_COLORS: Record<string, string> = {
  municipal: '#3b82c4', borewell: '#8b6cc1', recycled: '#1f7a4d', rainwater: '#2a9bb5',
}

export default function Water() {
  const period = usePeriod((s) => s.period)
  const q = useQuery({ queryKey: ['water', period], queryFn: () => get<WaterData>('/analytics/water/', periodParams(period)) })

  return (
    <>
      <PageHeader title="Water management"
        subtitle="Supply by source, consumption by zone and leak detection through night-time flow analysis."
        actions={<PeriodPicker />} />
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} retry={q.refetch} /> : q.data && <Body d={q.data} />}
    </>
  )
}

function Body({ d }: { d: WaterData }) {
  const sourceKeys = d.sources.map((s) => s.key)
  return (
    <>
      <div className="grid kpis">
        <Stat icon={<Droplets size={14} />} label="Consumption" value={num(d.totals.consumption_kl)} unit="kL" />
        <Stat label="Per person" value={num(d.totals.litres_per_person_day)} unit="L/day" />
        <Stat icon={<Recycle size={14} />} label="Recycled + harvested" value={num(d.totals.recycled_harvested_pct, 1)} unit="%"
          sub={`${num(d.totals.recycled_kl)} kL STP reuse`} />
        <Stat icon={<CloudRain size={14} />} label="Rainwater harvested" value={num(d.totals.rainwater_kl)} unit="kL" />
        <Stat icon={<IndianRupee size={14} />} label="Water cost" value={inr(d.totals.cost_inr)}
          sub={`${num(d.totals.tco2e, 2)} tCO₂e supply & treatment`} />
      </div>
      <div className="grid cols-3">
        <Card className="span-2" title="Daily supply by source" subtitle="kL per day">
          <ChartBox>
            <BarChart data={d.daily}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="date" tick={axis} tickFormatter={shortDate} minTickGap={24} />
              <YAxis tick={axis} tickFormatter={compact} width={44} />
              <Tooltip {...tooltipStyle} labelFormatter={(l) => shortDate(String(l))} formatter={(v) => `${num(Number(v), 1)} kL`} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {sourceKeys.map((k) => (
                <Bar key={k} dataKey={k} name={d.sources.find((s) => s.key === k)?.source} stackId="s" fill={SOURCE_COLORS[k] ?? '#999'} />
              ))}
            </BarChart>
          </ChartBox>
        </Card>
        <Card title="Supply mix" subtitle="Share of total supply">
          <ChartBox>
            <PieChart>
              <Pie data={d.sources} dataKey="kl" nameKey="source" innerRadius={50} outerRadius={90} paddingAngle={2}>
                {d.sources.map((s) => <Cell key={s.key} fill={SOURCE_COLORS[s.key] ?? '#999'} />)}
              </Pie>
              <Tooltip {...tooltipStyle} formatter={(v) => `${num(Number(v))} kL`} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          </ChartBox>
        </Card>
      </div>
      <Card title="Consumption and leak watch by building" className="mt" subtitle="Minimum flow between 01:00 and 05:00 should be close to zero; continuous night flow suggests a leak.">
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Building</th><th>Type</th><th className="num">kL</th><th className="num">L/occupant/day</th>
                <th className="num">Last night min. flow</th><th>Last 7 nights (kL/h)</th><th>Status</th></tr>
            </thead>
            <tbody>
              {d.buildings.map((b) => (
                <tr key={b.id}>
                  <td>{b.building}</td><td className="muted">{b.type}</td>
                  <td className="num">{num(b.kl)}</td><td className="num">{num(b.litres_per_occupant_day)}</td>
                  <td className="num">{b.latest_night_min_klph === null ? '–' : `${num(b.latest_night_min_klph, 2)} kL/h`}</td>
                  <td><Spark values={b.night_flow.map((n) => n.min_klph)} /></td>
                  <td>{b.leak_alert ? <Badge kind="high">leak alert open</Badge> : <Badge kind="ok">normal</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}

function Spark({ values }: { values: number[] }) {
  if (values.length < 2) return <span className="muted">–</span>
  const max = Math.max(...values, 0.1)
  const w = 110
  const h = 26
  const points = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - (v / max) * (h - 4) - 2}`).join(' ')
  return (
    <svg width={w} height={h} aria-hidden>
      <polyline points={points} fill="none" stroke="#2a9bb5" strokeWidth={2} />
    </svg>
  )
}
