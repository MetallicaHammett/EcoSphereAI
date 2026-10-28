import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Area, AreaChart, CartesianGrid, Cell, Legend, Pie, PieChart, Tooltip, XAxis, YAxis } from 'recharts'
import { Clock, Factory, IndianRupee, Sun, Zap } from 'lucide-react'
import { get } from '../api'
import { periodParams, usePeriod } from '../store'
import type { Building, EnergyData } from '../types'
import { Card, ErrorState, Loading, PageHeader, PeriodPicker, Segmented, Stat } from '../components/ui'
import { axis, ChartBox, COLORS, gridProps, PALETTE, tooltipStyle } from '../components/charts'
import { compact, dateTime, hourLabel, inr, num, shortDate } from '../format'

export default function Energy() {
  const period = usePeriod((s) => s.period)
  const [building, setBuilding] = useState('')
  const [granularity, setGranularity] = useState<'day' | 'hour'>('day')
  const buildings = useQuery({ queryKey: ['buildings'], queryFn: () => get<Building[]>('/buildings/') })
  const hourlyAllowed = period === '7'
  const gran = hourlyAllowed ? granularity : 'day'
  const q = useQuery({
    queryKey: ['energy', period, building, gran],
    queryFn: () => get<EnergyData>('/analytics/energy/', { ...periodParams(period), granularity: gran, ...(building && { building }) }),
  })

  return (
    <>
      <PageHeader title="Energy monitoring"
        subtitle="Grid draw, rooftop solar and demand by building and end use. Energy is usually the largest source of campus emissions."
        actions={
          <>
            <select value={building} onChange={(e) => setBuilding(e.target.value)} style={{ width: 'auto' }}>
              <option value="">Whole campus</option>
              {buildings.data?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <PeriodPicker />
          </>
        } />
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} retry={q.refetch} /> : q.data && (
        <>
          <div className="grid kpis">
            <Stat icon={<Zap size={14} />} label="Grid electricity" value={num(q.data.totals.grid_kwh)} unit="kWh" />
            <Stat icon={<Sun size={14} />} label="Solar generated" value={num(q.data.totals.solar_kwh)} unit="kWh"
              sub={`${num(q.data.totals.renewable_share_pct, 1)}% of consumption`} />
            <Stat icon={<Factory size={14} />} label="Scope 2 emissions" value={num(q.data.totals.tco2e, 1)} unit="tCO₂e" />
            <Stat icon={<IndianRupee size={14} />} label="Electricity cost" value={inr(q.data.totals.cost_inr)} />
            <Stat label="Peak demand" value={q.data.totals.peak_demand ? num(q.data.totals.peak_demand.kw) : '–'} unit="kW"
              sub={q.data.totals.peak_demand ? dateTime(q.data.totals.peak_demand.at) : undefined} />
            <Stat icon={<Clock size={14} />} label="Outside working hours" value={num(q.data.totals.after_hours_share_pct, 1)} unit="%"
              sub="Non-residential use nights, weekends, holidays" />
          </div>
          <Card title="Consumption over time" subtitle={`kWh per ${gran === 'hour' ? 'hour' : 'day'} · grid draw plus self-consumed solar`}
            actions={hourlyAllowed
              ? <Segmented value={granularity} onChange={setGranularity} options={[['day', 'Daily'], ['hour', 'Hourly']]} />
              : <span className="small muted">Hourly view available for 7 days</span>}>
            <ChartBox size="tall">
              <AreaChart data={q.data.series}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="t" tick={axis} tickFormatter={gran === 'hour' ? hourLabel : shortDate} minTickGap={30} />
                <YAxis tick={axis} tickFormatter={compact} width={48} />
                <Tooltip {...tooltipStyle} labelFormatter={(l) => (gran === 'hour' ? hourLabel(String(l)) : shortDate(String(l)))}
                  formatter={(v) => `${num(Number(v))} kWh`} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area type="monotone" dataKey="grid" name="Grid" stackId="1" stroke={COLORS.grid} fill={COLORS.grid} fillOpacity={0.35} />
                <Area type="monotone" dataKey="solar" name="Solar" stackId="1" stroke={COLORS.solar} fill={COLORS.solar} fillOpacity={0.5} />
              </AreaChart>
            </ChartBox>
          </Card>
          <div className="grid cols-3" style={{ marginTop: 16 }}>
            <Card className="span-2" title="By building" subtitle="Energy Performance Index annualised from this period">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Building</th><th>Type</th><th className="num">Grid kWh</th><th className="num">Solar kWh</th><th className="num">kWh/m²/yr</th></tr>
                  </thead>
                  <tbody>
                    {q.data.buildings.map((b) => (
                      <tr key={b.id}>
                        <td>{b.building}</td><td className="muted">{b.type}</td>
                        <td className="num">{num(b.grid_kwh)}</td><td className="num">{num(b.solar_kwh)}</td>
                        <td className="num"><b>{num(b.kwh_per_m2_yr, 0)}</b></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
            <Card title="By building type" subtitle="Share of total consumption">
              <ChartBox>
                <PieChart>
                  <Pie data={q.data.by_type} dataKey="kwh" nameKey="type" outerRadius={90} innerRadius={50} paddingAngle={2}>
                    {q.data.by_type.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                  </Pie>
                  <Tooltip {...tooltipStyle} formatter={(v) => `${num(Number(v))} kWh`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ChartBox>
            </Card>
          </div>
        </>
      )}
    </>
  )
}
