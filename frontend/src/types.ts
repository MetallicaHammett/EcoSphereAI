export interface Building {
  id: number
  name: string
  code: string
  type: string
  type_label: string
  area_m2: number
  occupants: number
  latitude: number | null
  longitude: number | null
}

export interface AlertItem {
  id: number
  building: number | null
  building_name: string | null
  meter_name: string | null
  category: string
  alert_type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  title: string
  message: string
  status: 'open' | 'acknowledged' | 'resolved'
  assigned_to: number | null
  assigned_to_name: string | null
  notes: string
  excess_quantity: number
  excess_unit: string
  estimated_cost: number
  occurred_on: string
  created_at: string
  resolved_at: string | null
}

export interface Peak {
  kw: number
  at: string
}

export interface Overview {
  range: { start: string; end: string; days: number; data_days: number }
  campus: { name: string; students: number; staff: number; area_m2: number; buildings: number }
  carbon: {
    total_tco2e: number
    annualised_tco2e: number
    per_student_t: number
    per_m2_kg: number
    scope1_t: number
    scope2_t: number
    scope3_t: number
    scope2_market_t: number
    sequestration_t_per_year: number
    grid_factor: number
  }
  by_category: { category: string; key: string; tco2e: number }[]
  by_building: { building: string; tco2e: number }[]
  monthly: { month: string; scope1: number; scope2: number; scope3: number }[]
  energy: { grid_kwh: number; solar_kwh: number; renewable_share_pct: number; eui_kwh_m2_yr: number; peak_demand: Peak | null; cost_inr: number }
  water: { consumption_kl: number; litres_per_person_day: number; recycled_harvested_pct: number; cost_inr: number }
  waste: { total_kg: number; per_person_day_kg: number; diversion_rate_pct: number; organic_treated_pct: number }
  transport: { survey_responses: number; sustainable_share_pct: number; fleet_diesel_l: number }
  target: null | {
    name: string
    baseline_year: number
    baseline_tco2e: number
    target_year: number
    target_tco2e: number
    reduction_pct_required: number
    reduction_achieved_pct: number
    progress_pct: number
  }
  alerts: { open: number; critical: number; recent: Pick<AlertItem, 'id' | 'title' | 'severity' | 'status' | 'category' | 'occurred_on'>[] }
  engagement: { active_users_30d: number; registered_users: number }
}

export interface EnergyData {
  granularity: 'hour' | 'day'
  series: { t: string; grid: number; solar: number; total: number }[]
  buildings: { id: number; building: string; type: string; grid_kwh: number; solar_kwh: number; kwh_per_m2_yr: number }[]
  by_type: { type: string; kwh: number }[]
  totals: {
    grid_kwh: number
    solar_kwh: number
    renewable_share_pct: number
    cost_inr: number
    tco2e: number
    after_hours_share_pct: number
    peak_demand: Peak | null
  }
}

export interface LiveData {
  updated_at: string | null
  buildings: {
    id: number
    building: string
    type: string
    type_label: string
    latitude: number | null
    longitude: number | null
    grid_kw: number
    solar_kw: number
    water_klph: number
    kw_per_100m2: number
    temperature: number | null
    humidity: number | null
    co2_ppm: number | null
    occupancy: number | null
    open_alerts: number
  }[]
  totals: { grid_kw: number; solar_kw: number; water_klph: number }
  weather: null | { temperature: number; humidity: number; irradiance: number; rainfall_mm: number; at: string }
  meters: { online: number; total: number }
}

export interface WaterData {
  daily: ({ date: string; kl: number } & Record<string, number | string>)[]
  sources: { source: string; key: string; kl: number; share_pct: number }[]
  buildings: {
    id: number
    building: string
    type: string
    kl: number
    litres_per_occupant_day: number
    night_flow: { date: string; min_klph: number }[]
    latest_night_min_klph: number | null
    leak_alert: boolean
  }[]
  totals: {
    consumption_kl: number
    litres_per_person_day: number
    recycled_harvested_pct: number
    rainwater_kl: number
    recycled_kl: number
    cost_inr: number
    tco2e: number
  }
}

export interface WasteData {
  weekly: ({ week: string } & Record<string, number | string>)[]
  by_category: { key: string; category: string; kg: number }[]
  by_disposal: { key: string; disposal: string; kg: number }[]
  totals: {
    total_kg: number
    diversion_rate_pct: number
    organic_treated_pct: number
    per_person_day_kg: number
    emitted_tco2e: number
    avoided_tco2e: number
    ewaste_kg: number
    hazardous_kg: number
  }
}

export interface TransportData {
  fleet: { asset: string; fuel: string; litres: number; km: number; km_per_litre: number; tco2e: number }[]
  modes: { mode: string; label: string; responses: number; share_pct: number; annual_tco2e: number; sustainable: boolean }[]
  totals: {
    fleet_litres: number
    fleet_km: number
    fleet_tco2e: number
    commute_annual_tco2e: number
    survey_responses: number
    sustainable_share_pct: number
    average_distance_km: number
  }
}

export interface Footprint {
  annual_km: number
  annual_kg: number
  per_trip_kg: number
  car_equivalent_kg: number
  saving_vs_car_kg: number
  trees_to_offset: number
  tip: string
}

export interface LeaderRow {
  id: number
  building: string
  type: string
  type_label: string
  kwh_per_occupant_day: number
  previous: number
  change_pct: number
  points: number
  rank: number
}

export interface Factor {
  id: number
  activity: string
  activity_label: string
  scope: number
  value: number
  activity_unit: string
  source: string
  valid_from: string
  version: number
  notes: string
  created_at: string
  created_by_name: string | null
}

export interface Meter {
  id: number
  building: number | null
  building_name: string | null
  name: string
  serial: string
  kind: string
  kind_label: string
  source: string
  unit: string
  capacity: number
  max_value: number
  is_active: boolean
  last_reading_at: string | null
  online: boolean
}
