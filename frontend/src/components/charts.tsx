import type { ReactElement } from 'react'
import { ResponsiveContainer } from 'recharts'

export const COLORS = {
  scope1: '#e07a3f',
  scope2: '#3b82c4',
  scope3: '#8b6cc1',
  grid: '#3b82c4',
  solar: '#f2b33d',
  water: '#2a9bb5',
  primary: '#1f7a4d',
  forecast: '#1f7a4d',
  muted: '#9aa9a1',
  danger: '#c2410c',
}

export const PALETTE = ['#1f7a4d', '#3b82c4', '#e07a3f', '#8b6cc1', '#f2b33d', '#2a9bb5', '#d14d72', '#7a8b2f',
  '#5d6f65', '#b5651d']

export const axis = { fontSize: 12, fill: '#5d6f65' }
export const gridProps = { strokeDasharray: '3 3', stroke: '#e5ece8', vertical: false }
export const tooltipStyle = {
  contentStyle: { borderRadius: 8, border: '1px solid #e1e8e4', fontSize: 12.5, boxShadow: '0 4px 14px rgba(0,0,0,.08)' },
  labelStyle: { fontWeight: 600, color: '#15241c' },
}

export function ChartBox({ children, size = '' }: { children: ReactElement; size?: '' | 'tall' | 'short' }) {
  return (
    <div className={`chart ${size}`}>
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  )
}
