import { useState } from 'react'
import toast from 'react-hot-toast'
import { Download, FileSpreadsheet, FileText } from 'lucide-react'
import { download, errorMessage } from '../api'
import { Card, Field, PageHeader } from '../components/ui'
import { localISODate } from '../format'

const DATASETS: [string, string][] = [
  ['emissions', 'Emission line items (all scopes)'],
  ['electricity', 'Daily electricity by building'],
  ['solar', 'Daily solar generation by building'],
  ['water', 'Daily water consumption by building'],
  ['waste', 'Waste weighings'],
  ['fuel', 'Fuel & refrigerant logs'],
  ['alerts', 'Alerts & work orders'],
  ['factors', 'Emission factor register'],
]

const FRAMEWORKS = [
  ['GHG Protocol Corporate Standard', 'Scope 1, 2 (location & market based) and Scope 3 inventory in the PDF report.'],
  ['ISO 14064-1 / ISO 50001', 'Version-controlled factors, documented boundary and baseline; EnPI (kWh/m²) tracking.'],
  ['CEA CO₂ Baseline Database', 'Grid emission factor stored as a dated, versioned parameter - update when CEA publishes.'],
  ['GRIHA / IGBC', 'Energy Performance Index, water L/person/day, waste diversion and renewable share KPIs.'],
  ['AASHE STARS & NIRF disclosures', 'Per-student emissions, commuting mode share, green cover and engagement indicators.'],
  ['UN SDGs 7, 11, 12, 13', 'Clean energy, sustainable campus operations, responsible consumption and climate action.'],
]

const iso = localISODate

export default function Reports() {
  const today = new Date()
  const [start, setStart] = useState(iso(new Date(today.getFullYear(), 0, 1)))
  const [end, setEnd] = useState(iso(today))
  const [dataset, setDataset] = useState('emissions')
  const [busy, setBusy] = useState('')

  async function run(kind: 'pdf' | 'csv') {
    if (end < start) {
      toast.error('End date must be after the start date.')
      return
    }
    setBusy(kind)
    try {
      if (kind === 'pdf') await download('/reports/ghg.pdf', { start, end }, 'ghg-inventory.pdf')
      else await download('/reports/export.csv', { start, end, dataset }, `${dataset}.csv`)
      toast.success('Download started')
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setBusy('')
    }
  }

  return (
    <>
      <PageHeader title="Reports & exports"
        subtitle="Automated, consistent reporting so results are comparable year on year." />
      <Card title="Reporting period">
        <div className="form-row" style={{ maxWidth: 420 }}>
          <Field label="From"><input type="date" value={start} max={end} onChange={(e) => setStart(e.target.value)} /></Field>
          <Field label="To"><input type="date" value={end} max={iso(today)} onChange={(e) => setEnd(e.target.value)} /></Field>
        </div>
      </Card>
      <div className="grid cols-2 mt">
        <Card title="GHG inventory report (PDF)" subtitle="Summary KPIs, emissions by scope, source, building and month, target progress, methodology and factor table.">
          <button className="btn primary" disabled={!!busy} onClick={() => run('pdf')}>
            <FileText size={15} /> {busy === 'pdf' ? 'Generating…' : 'Download PDF report'}
          </button>
        </Card>
        <Card title="Data export (CSV)" subtitle="Open in Excel, LibreOffice or Python for further analysis.">
          <div className="row">
            <select value={dataset} onChange={(e) => setDataset(e.target.value)} style={{ flex: 1, minWidth: 200 }}>
              {DATASETS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <button className="btn" disabled={!!busy} onClick={() => run('csv')}>
              {busy === 'csv' ? <Download size={15} /> : <FileSpreadsheet size={15} />} {busy === 'csv' ? 'Exporting…' : 'Export CSV'}
            </button>
          </div>
        </Card>
      </div>
      <Card className="mt" title="Standards and frameworks supported">
        <div className="table-wrap">
          <table>
            <tbody>
              {FRAMEWORKS.map(([name, how]) => (
                <tr key={name}><td><b>{name}</b></td><td className="wrap muted">{how}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}
