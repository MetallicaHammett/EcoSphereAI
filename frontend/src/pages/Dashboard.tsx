import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ReferenceLine, Tooltip, XAxis, YAxis,
} from 'recharts'
import { AlertTriangle, Droplets, Factory, Gauge, Recycle, Sun, Target, Users } from 'lucide-react'
import { get } from '../api'
import { periodParams, usePeriod } from '../store'
import type { Overview } from '../types'
import { Badge, Card, ErrorState, Loading, PageHeader, PeriodPicker, Progress, Stat } from '../components/ui'
import { axis, ChartBox, COLORS, gridProps, PALETTE, tooltipStyle } from '../components/charts'
import { inr, monthLabel, num } from '../format'

export default function Dashboard() {
  const period = usePeriod((s) => s.period)
  const q = useQuery({
    queryKey: ['overview', period],
    queryFn: () => get<Overview>('/analytics/overview/', periodParams(period)),
  })

  return (
    <>
      <PageHeader
        title="Management dashboard"
        subtitle={q.data ? `${q.data.campus.name} · ${q.data.campus.buildings} buildings · ${num(q.data.campus.students)} students` : 'Campus-wide emissions, resources and progress against target'}
        actions={<PeriodPicker />}
      />
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} retry={q.refetch} /> : q.data && <Body d={q.data} />}
    </>
  )
}

function Body({ d }: { d: Overview }) {
  const c = d.carbon
  const scopes = [
    { name: 'Scope 1 · direct', value: c.scope1_t, color: COLORS.scope1 },
    { name: 'Scope 2 · electricity', value: c.scope2_t, color: COLORS.scope2 },
    { name: 'Scope 3 · value chain', value: c.scope3_t, color: COLORS.scope3 },
  ]
  const monthly = d.monthly.map((m) => ({ ...m, label: monthLabel(m.month) }))
  const targetMonthly = d.target ? d.target.target_tco2e / 12 : null
  const baselineMonthly = d.target ? d.target.baseline_tco2e / 12 : null
  const partial = d.range.data_days < d.range.days

  return (
    <>
      {partial && (
        <div className="notice" style={{ marginBottom: 16 }}>
          Monitoring data covers {d.range.data_days} of the {d.range.days} days in this period; annualised figures use
          the days with data.
        </div>
      )}
      <div className="grid kpis">
        <Stat icon={<Factory size={14} />} label="Total emissions" value={num(c.total_tco2e, 1)} unit="tCO₂e"
          sub={`${num(c.annualised_tco2e)} t/yr annualised`} />
        <Stat icon={<Users size={14} />} label="Per student" value={num(c.per_student_t, 2)} unit="t/yr"
          sub={`${num(c.per_m2_kg, 1)} kgCO₂e per m²`} />
        <Stat icon={<Sun size={14} />} label="Renewable electricity" value={num(d.energy.renewable_share_pct, 1)} unit="%"
          sub={`${num(d.energy.solar_kwh)} kWh rooftop solar`} />
        <Stat icon={<Gauge size={14} />} label="Energy intensity" value={num(d.energy.eui_kwh_m2_yr, 0)} unit="kWh/m²/yr"
          sub={d.energy.peak_demand ? `Peak ${num(d.energy.peak_demand.kw)} kW` : undefined} />
        <Stat icon={<Droplets size={14} />} label="Water use" value={num(d.water.litres_per_person_day, 0)} unit="L/person/day"
          sub={`${num(d.water.recycled_harvested_pct, 0)}% recycled or harvested`} />
        <Stat icon={<Recycle size={14} />} label="Waste diversion" value={num(d.waste.diversion_rate_pct, 0)} unit="%"
          sub={`${num(d.waste.organic_treated_pct, 0)}% of organic waste composted`} />
        <Stat icon={<AlertTriangle size={14} />} label="Open alerts" value={d.alerts.open}
          sub={`${d.alerts.critical} high or critical`} />
        <Stat icon={<Target size={14} />} label="Utility spend" value={inr(d.energy.cost_inr + d.water.cost_inr)}
          sub="Electricity + water, this period" />
      </div>

      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        <Card className="span-2" title="Monthly emissions by scope" subtitle="tCO₂e · dashed lines show monthly baseline and target pace">
          <ChartBox>
            <BarChart data={monthly}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="label" tick={axis} />
              <YAxis tick={axis} width={48}
                domain={[0, (max: number) => Math.ceil(Math.max(max, baselineMonthly ?? 0) * 1.08)]} />
              <Tooltip {...tooltipStyle} formatter={(v) => `${num(Number(v), 1)} t`} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="scope1" name="Scope 1" stackId="s" fill={COLORS.scope1} />
              <Bar dataKey="scope2" name="Scope 2" stackId="s" fill={COLORS.scope2} />
              <Bar dataKey="scope3" name="Scope 3" stackId="s" fill={COLORS.scope3} radius={[4, 4, 0, 0]} />
              {baselineMonthly && <ReferenceLine y={baselineMonthly} stroke={COLORS.muted} strokeDasharray="5 4"
                label={{ value: 'Baseline', fontSize: 11, fill: '#5d6f65', position: 'insideTopRight' }} />}
              {targetMonthly && <ReferenceLine y={targetMonthly} stroke={COLORS.primary} strokeDasharray="5 4"
                label={{ value: `${d.target?.target_year} target`, fontSize: 11, fill: COLORS.primary, position: 'insideBottomRight' }} />}
            </BarChart>
          </ChartBox>
        </Card>
        <Card title="Scope split" subtitle="GHG Protocol, location-based">
          <ChartBox size="short">
            <PieChart>
              <Pie data={scopes} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                {scopes.map((s) => <Cell key={s.name} fill={s.color} />)}
              </Pie>
              <Tooltip {...tooltipStyle} formatter={(v) => `${num(Number(v), 1)} t`} />
            </PieChart>
          </ChartBox>
          <div className="list small">
            {scopes.map((s) => (
              <div className="row" key={s.name}>
                <span className="dot" style={{ background: s.color }} /> {s.name}
                <span className="spacer" />
                <b>{num(s.value, 1)} t</b>
                <span className="muted">{num((s.value / Math.max(c.total_tco2e, 0.001)) * 100, 0)}%</span>
              </div>
            ))}
            <div className="muted" style={{ marginTop: 8 }}>
              Market-based Scope 2: {num(c.scope2_market_t, 1)} t · grid factor {c.grid_factor} kg/kWh
            </div>
          </div>
        </Card>
      </div>

      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        <Card title="Emissions by source" subtitle="tCO₂e this period">
          <ChartBox>
            <BarChart data={d.by_category} layout="vertical" margin={{ left: 10 }}>
              <CartesianGrid {...gridProps} horizontal={false} vertical />
              <XAxis type="number" tick={axis} />
              <YAxis type="category" dataKey="category" tick={axis} width={150} />
              <Tooltip {...tooltipStyle} formatter={(v) => `${num(Number(v), 2)} t`} />
              <Bar dataKey="tco2e" name="tCO₂e" radius={[0, 4, 4, 0]}>
                {d.by_category.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              </Bar>
            </BarChart>
          </ChartBox>
        </Card>
        <Card title="Emissions by building" subtitle="Electricity, water and logged sources">
          <ChartBox>
            <BarChart data={d.by_building} layout="vertical" margin={{ left: 10 }}>
              <CartesianGrid {...gridProps} horizontal={false} vertical />
              <XAxis type="number" tick={axis} />
              <YAxis type="category" dataKey="building" tick={axis} width={130} />
              <Tooltip {...tooltipStyle} formatter={(v) => `${num(Number(v), 2)} t`} />
              <Bar dataKey="tco2e" name="tCO₂e" fill={COLORS.scope2} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ChartBox>
        </Card>
        <div className="stack">
          {d.target && (
            <Card title="Progress to target" subtitle={d.target.name}>
              <div className="row" style={{ marginBottom: 8 }}>
                <span className="stat-value">{num(d.target.progress_pct)}%</span>
                <span className="muted small">of the way to −{d.target.reduction_pct_required}% by {d.target.target_year}</span>
              </div>
              <Progress value={d.target.progress_pct} />
              <p className="small muted" style={{ marginBottom: 0 }}>
                Baseline {d.target.baseline_year}: {num(d.target.baseline_tco2e)} t · now {num(c.annualised_tco2e)} t/yr
                ({d.target.reduction_achieved_pct > 0 ? '−' : '+'}{num(Math.abs(d.target.reduction_achieved_pct), 1)}%) ·
                target {num(d.target.target_tco2e)} t
              </p>
            </Card>
          )}
          <Card title="Latest alerts" actions={<Link className="small" to="/operations">View all</Link>}>
            {d.alerts.recent.length === 0 ? <p className="muted">No open alerts. All systems normal.</p> : (
              <div className="list">
                {d.alerts.recent.map((a) => (
                  <div className="list-item" key={a.id}>
                    <Badge kind={a.severity}>{a.severity}</Badge>
                    <span className="small">{a.title}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
      <p className="small muted">
        Tree sequestration ({num(c.sequestration_t_per_year, 1)} tCO₂/yr) is reported separately and never netted
        against emissions.
      </p>
    </>
  )
}
