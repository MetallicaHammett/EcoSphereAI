import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from 'recharts'
import { Sprout, Trees } from 'lucide-react'
import { get } from '../api'
import { Card, ErrorState, Loading, PageHeader, Stat } from '../components/ui'
import { axis, ChartBox, COLORS, gridProps, tooltipStyle } from '../components/charts'
import { num } from '../format'

interface GreenData {
  species: { id: number; species: string; zone: string; count: number; planted_year: number | null; tco2_per_year: number; canopy_m2: number }[]
  totals: { trees: number; species: number; canopy_m2: number; sequestration_tco2_per_year: number; annual_emissions_tco2e: number; offset_pct: number }
  note: string
}

export default function Green() {
  const q = useQuery({ queryKey: ['green'], queryFn: () => get<GreenData>('/analytics/green/') })
  return (
    <>
      <PageHeader title="Green cover & biodiversity" subtitle="Tree inventory, canopy area and conservatively estimated carbon sequestration." />
      {q.isLoading ? <Loading /> : q.isError ? <ErrorState error={q.error} retry={q.refetch} /> : q.data && (
        <>
          <div className="grid kpis">
            <Stat icon={<Trees size={14} />} label="Trees on campus" value={num(q.data.totals.trees)} sub={`${q.data.totals.species} species`} />
            <Stat label="Canopy area" value={num(q.data.totals.canopy_m2)} unit="m²" />
            <Stat icon={<Sprout size={14} />} label="Sequestration" value={num(q.data.totals.sequestration_tco2_per_year, 1)} unit="tCO₂/yr" />
            <Stat label="Compared with emissions" value={num(q.data.totals.offset_pct, 2)} unit="%"
              sub={`of ${num(q.data.totals.annual_emissions_tco2e)} tCO₂e/yr`} />
          </div>
          <div className="notice" style={{ marginBottom: 16 }}>{q.data.note}</div>
          <div className="grid cols-2">
            <Card title="Sequestration by species" subtitle="tCO₂ per year">
              <ChartBox>
                <BarChart data={q.data.species}>
                  <CartesianGrid {...gridProps} />
                  <XAxis dataKey="species" tick={axis} interval={0} angle={-20} textAnchor="end" height={50} />
                  <YAxis tick={axis} width={40} />
                  <Tooltip {...tooltipStyle} formatter={(v) => `${num(Number(v), 2)} t/yr`} />
                  <Bar dataKey="tco2_per_year" name="tCO₂/yr" fill={COLORS.primary} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ChartBox>
            </Card>
            <Card title="Tree inventory">
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Species</th><th>Zone</th><th className="num">Count</th><th className="num">Canopy m²</th><th className="num">tCO₂/yr</th></tr></thead>
                  <tbody>
                    {q.data.species.map((s) => (
                      <tr key={s.id}><td>{s.species}</td><td className="muted">{s.zone}</td><td className="num">{num(s.count)}</td>
                        <td className="num">{num(s.canopy_m2)}</td><td className="num">{num(s.tco2_per_year, 2)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        </>
      )}
    </>
  )
}
