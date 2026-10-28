import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'
import { api, get } from '../api'
import { periodParams, usePeriod } from '../store'
import type { Building } from '../types'
import { Card, ErrorState, Loading, PageHeader, PeriodPicker, Segmented, Stars, Stat } from '../components/ui'
import { axis, ChartBox, COLORS, gridProps, tooltipStyle } from '../components/charts'
import { compact, inr, num, shortDate } from '../format'

type Tab = 'forecast' | 'scenarios' | 'benchmark'

export default function Insights() {
  const [tab, setTab] = useState<Tab>('forecast')
  return (
    <>
      <PageHeader title="Forecasts, scenarios & benchmarking"
        subtitle="Predict demand for budgeting and peak management, test interventions before spending money, and compare buildings fairly." />
      <div className="tabs">
        {([['forecast', 'Demand forecast'], ['scenarios', 'Scenario modelling'], ['benchmark', 'Building benchmarking']] as [Tab, string][]).map(([k, l]) => (
          <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === 'forecast' && <Forecast />}
      {tab === 'scenarios' && <Scenarios />}
      {tab === 'benchmark' && <Benchmark />}
    </>
  )
}

// ------------------------------------------------------------------ forecast

interface ForecastData {
  history: { date: string; actual: number; fitted: number; non_working: boolean }[]
  forecast: { date: string; forecast: number; lower: number; upper: number; non_working: boolean }[]
  model: { method: string; training_days: number; mape_pct: number; r2: number; assumed_temperature_c: number; temperature_sensitivity_kwh_per_c: number }
  totals: { kwh: number; tco2e: number; cost: number; peak_day: string | null }
}

function Forecast() {
  const [horizon, setHorizon] = useState<'14' | '30' | '60'>('30')
  const [building, setBuilding] = useState('')
  const buildings = useQuery({ queryKey: ['buildings'], queryFn: () => get<Building[]>('/buildings/') })
  const q = useQuery({
    queryKey: ['forecast', horizon, building],
    queryFn: () => get<ForecastData>('/analytics/forecast/', { days: horizon, ...(building && { building }) }),
  })
  const data = q.data ? [
    ...q.data.history.map((h) => ({ date: h.date, actual: h.actual, fitted: h.fitted })),
    ...q.data.forecast.map((f) => ({ date: f.date, forecast: f.forecast, band: [f.lower, f.upper] })),
  ] : []
  const today = q.data?.forecast[0]?.date

  return (
    <>
      <div className="row" style={{ marginBottom: 16 }}>
        <select value={building} onChange={(e) => setBuilding(e.target.value)} style={{ width: 'auto' }}>
          <option value="">Whole campus</option>
          {buildings.data?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
        <Segmented value={horizon} onChange={setHorizon} options={[['14', '14 days'], ['30', '30 days'], ['60', '60 days']]} />
      </div>
      {q.isLoading ? <Loading label="Training model…" /> : q.isError ? <ErrorState error={q.error} retry={q.refetch} /> : q.data && (
        <>
          <div className="grid kpis">
            <Stat label={`Forecast electricity (${horizon} d)`} value={num(q.data.totals.kwh)} unit="kWh" />
            <Stat label="Forecast emissions" value={num(q.data.totals.tco2e, 1)} unit="tCO₂e" />
            <Stat label="Forecast bill" value={inr(q.data.totals.cost)} />
            <Stat label="Peak day" value={q.data.totals.peak_day ? shortDate(q.data.totals.peak_day) : '–'} />
            <Stat label="Model accuracy" value={num(100 - q.data.model.mape_pct, 1)} unit="%"
              sub={`MAPE ${q.data.model.mape_pct}% · R² ${q.data.model.r2}`} />
          </div>
          <Card title="Daily grid electricity: actual, fitted and forecast" subtitle="Shaded band = 95% prediction interval">
            <ChartBox size="tall">
              <ComposedChart data={data}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="date" tick={axis} tickFormatter={shortDate} minTickGap={24} />
                <YAxis tick={axis} tickFormatter={compact} width={48} />
                <Tooltip {...tooltipStyle} labelFormatter={(l) => shortDate(String(l))}
                  formatter={(v) => (Array.isArray(v) ? `${num(Number(v[0]))} – ${num(Number(v[1]))} kWh` : `${num(Number(v))} kWh`)} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area dataKey="band" name="95% interval" stroke="none" fill={COLORS.forecast} fillOpacity={0.15} />
                <Line dataKey="actual" name="Actual" stroke={COLORS.grid} dot={false} strokeWidth={2} />
                <Line dataKey="fitted" name="Model fit" stroke={COLORS.muted} dot={false} strokeDasharray="4 3" />
                <Line dataKey="forecast" name="Forecast" stroke={COLORS.forecast} dot={false} strokeWidth={2.5} />
                {today && <ReferenceLine x={today} stroke="#5d6f65" strokeDasharray="3 3" label={{ value: 'Today', fontSize: 11, fill: '#5d6f65' }} />}
              </ComposedChart>
            </ChartBox>
          </Card>
          <Card className="mt" title="About the model">
            <p className="small" style={{ margin: 0 }}>
              {q.data.model.method}. Trained on {q.data.model.training_days} days using the academic calendar (weekends, holidays,
              vacations) and outdoor temperature. Each +1 °C adds about <b>{num(q.data.model.temperature_sensitivity_kwh_per_c)} kWh/day</b> of
              cooling load. Future days assume {q.data.model.assumed_temperature_c} °C (recent average).
            </p>
          </Card>
        </>
      )}
    </>
  )
}

// ------------------------------------------------------------------ scenarios

interface ScenarioResult {
  baseline: { annual_grid_kwh: number; annual_grid_tco2e: number; grid_factor: number; tariff: number }
  measures: { key: string; name: string; kwh_saved: number; diesel_l_saved: number; tco2e_saved: number; annual_saving_inr: number; capex_inr: number; payback_years: number | null; note: string }[]
  totals: { kwh_saved: number; tco2e_saved: number; annual_saving_inr: number; capex_inr: number; payback_years: number | null; electricity_reduction_pct: number }
}

const LEVERS = [
  { key: 'led_coverage_pct', label: 'LED retrofit of remaining lighting', unit: '%', min: 0, max: 100, step: 5, initial: 50 },
  { key: 'solar_kwp', label: 'Additional rooftop solar', unit: 'kWp', min: 0, max: 1500, step: 50, initial: 250 },
  { key: 'setpoint_increase_c', label: 'Raise AC set-points by', unit: '°C', min: 0, max: 4, step: 0.5, initial: 1 },
  { key: 'smart_controls_pct', label: 'Occupancy-based controls coverage', unit: '%', min: 0, max: 100, step: 10, initial: 30 },
  { key: 'electric_buses', label: 'Diesel buses replaced with electric', unit: '', min: 0, max: 6, step: 1, initial: 0 },
] as const

function Scenarios() {
  const [values, setValues] = useState<Record<string, number>>(Object.fromEntries(LEVERS.map((l) => [l.key, l.initial])))
  const [debounced, setDebounced] = useState(values)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(values), 300)
    return () => clearTimeout(t)
  }, [values])
  const q = useQuery({
    queryKey: ['scenario', debounced],
    queryFn: async () => (await api.post<ScenarioResult>('/analytics/scenarios/', debounced)).data,
    placeholderData: keepPreviousData,
  })

  return (
    <div className="grid cols-3">
      <Card title="Interventions" subtitle="Move the sliders; results update instantly">
        <div className="form">
          {LEVERS.map((l) => (
            <div className="range-field" key={l.key}>
              <div className="top"><span>{l.label}</span><b>{values[l.key]} {l.unit}</b></div>
              <input type="range" min={l.min} max={l.max} step={l.step} value={values[l.key]}
                onChange={(e) => setValues({ ...values, [l.key]: Number(e.target.value) })} />
            </div>
          ))}
          {q.data && (
            <p className="small muted" style={{ margin: 0 }}>
              Baseline: {num(q.data.baseline.annual_grid_kwh)} kWh/yr grid electricity ({num(q.data.baseline.annual_grid_tco2e)} tCO₂e),
              annualised from the last 30 days · tariff ₹{q.data.baseline.tariff}/kWh.
            </p>
          )}
        </div>
      </Card>
      <div className="span-2 stack">
        {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} retry={q.refetch} /> : q.data && (
          <>
            <div className="grid kpis" style={{ marginBottom: 0 }}>
              <Stat label="Emissions avoided" value={num(q.data.totals.tco2e_saved)} unit="tCO₂e/yr" />
              <Stat label="Electricity reduction" value={num(q.data.totals.electricity_reduction_pct, 1)} unit="%" />
              <Stat label="Annual savings" value={inr(q.data.totals.annual_saving_inr)} />
              <Stat label="Investment" value={inr(q.data.totals.capex_inr)}
                sub={q.data.totals.payback_years !== null ? `Payback ${q.data.totals.payback_years} years` : undefined} />
            </div>
            <Card title="Impact by measure">
              <ChartBox size="short">
                <BarChart data={q.data.measures}>
                  <CartesianGrid {...gridProps} />
                  <XAxis dataKey="name" tick={{ ...axis, fontSize: 11 }} interval={0}
                    tickFormatter={(v) => String(v).split(' ').slice(0, 2).join(' ')} />
                  <YAxis tick={axis} width={40} />
                  <Tooltip {...tooltipStyle} formatter={(v) => `${num(Number(v), 1)} tCO₂e/yr`} />
                  <Bar dataKey="tco2e_saved" name="tCO₂e avoided" radius={[4, 4, 0, 0]}>
                    {q.data.measures.map((m) => <Cell key={m.key} fill={m.tco2e_saved >= 0 ? COLORS.primary : COLORS.danger} />)}
                  </Bar>
                </BarChart>
              </ChartBox>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Measure</th><th className="num">tCO₂e/yr</th><th className="num">Saving/yr</th><th className="num">Cost</th><th className="num">Payback</th><th>Assumption</th></tr></thead>
                  <tbody>
                    {q.data.measures.map((m) => (
                      <tr key={m.key}>
                        <td>{m.name}</td><td className="num">{num(m.tco2e_saved, 1)}</td><td className="num">{inr(m.annual_saving_inr)}</td>
                        <td className="num">{m.capex_inr ? inr(m.capex_inr) : 'No cost'}</td>
                        <td className="num">{m.payback_years === null ? 'n/a' : m.payback_years === 0 ? 'Immediate' : `${m.payback_years} yr`}</td>
                        <td className="wrap small muted">{m.note}</td>
                      </tr>
                    ))}
                    {!q.data.measures.length && <tr><td colSpan={6} className="muted">Move a slider to model an intervention.</td></tr>}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ benchmarking

interface BenchmarkData {
  buildings: { id: number; building: string; type: string; area_m2: number; occupants: number; eui_kwh_m2_yr: number; kwh_per_occupant_day: number; water_l_per_occupant_day: number; tco2e: number; stars: number; rank: number }[]
  days: number
  note: string
}

function Benchmark() {
  const period = usePeriod((s) => s.period)
  const q = useQuery({ queryKey: ['benchmark', period], queryFn: () => get<BenchmarkData>('/analytics/benchmark/', periodParams(period)) })
  return (
    <>
      <div className="row" style={{ marginBottom: 16 }}><PeriodPicker /></div>
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} retry={q.refetch} /> : q.data && (
        <div className="grid cols-2">
          <Card title="Energy Performance Index" subtitle="kWh per m² per year · lower is better">
            <ChartBox size="tall">
              <BarChart data={q.data.buildings} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid {...gridProps} horizontal={false} vertical />
                <XAxis type="number" tick={axis} />
                <YAxis type="category" dataKey="building" tick={axis} width={140} />
                <Tooltip {...tooltipStyle} formatter={(v) => `${num(Number(v), 1)} kWh/m²/yr`} />
                <Bar dataKey="eui_kwh_m2_yr" name="EPI" radius={[0, 4, 4, 0]}>
                  {q.data.buildings.map((b) => <Cell key={b.id} fill={b.stars >= 4 ? COLORS.primary : b.stars === 3 ? COLORS.solar : COLORS.scope1} />)}
                </Bar>
              </BarChart>
            </ChartBox>
          </Card>
          <Card title="League table" subtitle={q.data.note}>
            <div className="table-wrap">
              <table>
                <thead><tr><th>#</th><th>Building</th><th className="num">kWh/m²/yr</th><th className="num">kWh/person/day</th><th className="num">Water L/person/day</th><th>Rating</th></tr></thead>
                <tbody>
                  {q.data.buildings.map((b) => (
                    <tr key={b.id}>
                      <td>{b.rank}</td><td>{b.building}<div className="small muted">{b.type}</div></td>
                      <td className="num">{num(b.eui_kwh_m2_yr, 0)}</td><td className="num">{num(b.kwh_per_occupant_day, 2)}</td>
                      <td className="num">{num(b.water_l_per_occupant_day)}</td><td><Stars count={b.stars} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </>
  )
}
