"""
Scenario modelling: estimate savings from interventions before money is spent.
Assumptions are explicit inputs with sensible Indian-campus defaults so they can be challenged.
"""

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from monitoring.models import Building, CampusSettings, Meter
from sustainability.models import FuelLog

from .carbon import FactorBook
from .common import data_days, day_start, readings

DEFAULTS = {
    "led_coverage_pct": 50.0,       # share of remaining non-LED lighting to retrofit
    "lighting_share_pct": 20.0,     # lighting share of campus electricity
    "led_saving_pct": 50.0,         # LED vs fluorescent saving
    "led_cost_per_m2": 120.0,       # INR per m2 of floor area retrofitted
    "solar_kwp": 0.0,
    "solar_yield_kwh_per_kwp": 1400.0,
    "solar_cost_per_kwp": 45000.0,
    "setpoint_increase_c": 0.0,
    "cooling_share_pct": 45.0,
    "saving_per_degree_pct": 6.0,
    "smart_controls_pct": 0.0,      # share of non-residential floor area with occupancy-based controls
    "smart_controls_saving_pct": 15.0,
    "smart_controls_cost_per_m2": 150.0,
    "electric_buses": 0,
    "bus_km_per_year": 30000.0,
    "diesel_bus_km_per_litre": 4.0,
    "ebus_kwh_per_km": 1.1,
    "ebus_extra_cost": 8000000.0,
}


def _num(params, key):
    try:
        value = float(params.get(key, DEFAULTS[key]))
    except (TypeError, ValueError):
        value = DEFAULTS[key]
    return max(value, 0.0)


def baseline_annual():
    """Annualised campus grid electricity and total footprint from the last 30 days of data."""
    end = timezone.localdate()
    start = end - timedelta(days=30)
    qs = readings(Meter.Kind.ELECTRICITY, start=day_start(start), end=day_start(end))
    days = data_days(qs) or 1
    kwh = (qs.aggregate(t=Sum("value"))["t"] or 0) * 365 / days
    fleet = FuelLog.objects.filter(category=FuelLog.Category.FLEET, date__gte=start, date__lt=end)
    buses = fleet.values("asset").distinct().count()
    km = fleet.aggregate(k=Sum("distance_km"))["k"] or 0
    return kwh, (km * 365 / 30 / buses) if buses else None


def run(params):
    p = {k: _num(params, k) for k in DEFAULTS}
    settings = CampusSettings.load()
    book = FactorBook()
    grid = book.value("electricity_grid")
    diesel = book.value("diesel")
    annual_kwh, bus_km = baseline_annual()
    if bus_km and "bus_km_per_year" not in params:
        p["bus_km_per_year"] = bus_km
    non_res_area = sum(b.area_m2 for b in Building.objects.exclude(type=Building.Type.HOSTEL))
    total_area = sum(b.area_m2 for b in Building.objects.all())
    measures = []

    def add(key, name, kwh=0.0, litres=0.0, extra_kwh=0.0, capex=0.0, note=""):
        net_kwh = kwh - extra_kwh
        tco2e = (net_kwh * grid + litres * diesel) / 1000
        saving = net_kwh * settings.electricity_tariff + litres * settings.diesel_price
        measures.append({
            "key": key, "name": name, "kwh_saved": round(net_kwh), "diesel_l_saved": round(litres),
            "tco2e_saved": round(tco2e, 1), "annual_saving_inr": round(saving), "capex_inr": round(capex),
            "payback_years": round(capex / saving, 1) if saving > 0 and capex else (0 if saving > 0 else None),
            "note": note,
        })

    lighting_kwh = annual_kwh * p["lighting_share_pct"] / 100
    cooling_kwh = annual_kwh * p["cooling_share_pct"] / 100
    if p["led_coverage_pct"]:
        cov = min(p["led_coverage_pct"], 100) / 100
        add("led", "LED lighting retrofit", kwh=lighting_kwh * cov * p["led_saving_pct"] / 100,
            capex=total_area * cov * p["led_cost_per_m2"],
            note=f"{cov:.0%} of non-LED lighting replaced; LEDs use ~{p['led_saving_pct']:.0f}% less energy.")
    if p["solar_kwp"]:
        add("solar", "Rooftop solar expansion", kwh=p["solar_kwp"] * p["solar_yield_kwh_per_kwp"],
            capex=p["solar_kwp"] * p["solar_cost_per_kwp"],
            note=f"{p['solar_kwp']:.0f} kWp at {p['solar_yield_kwh_per_kwp']:.0f} kWh/kWp/year (Chennai typical).")
    if p["setpoint_increase_c"]:
        deg = min(p["setpoint_increase_c"], 5)
        add("setpoint", "Air-conditioning set-point increase",
            kwh=cooling_kwh * min(deg * p["saving_per_degree_pct"] / 100, 0.5),
            note=f"Raise set-points by {deg:.1f} C (e.g. 22 to {22 + deg:.0f} C, within BEE's 24 C default).")
    if p["smart_controls_pct"]:
        share = min(p["smart_controls_pct"], 100) / 100
        add("controls", "Occupancy-based HVAC & lighting controls",
            kwh=(cooling_kwh + lighting_kwh) * share * p["smart_controls_saving_pct"] / 100,
            capex=non_res_area * share * p["smart_controls_cost_per_m2"],
            note="Switches cooling and lights off in empty rooms using occupancy sensors.")
    if p["electric_buses"]:
        n = int(p["electric_buses"])
        km = n * p["bus_km_per_year"]
        add("ebus", "Electric campus buses", litres=km / p["diesel_bus_km_per_litre"],
            extra_kwh=km * p["ebus_kwh_per_km"], capex=n * p["ebus_extra_cost"],
            note=f"{n} diesel bus(es) replaced; charging electricity is counted against the saving. On today's "
                 "grid the carbon gain is small or negative unless buses are charged from solar.")

    totals = {k: sum(m[k] for m in measures) for k in
              ("kwh_saved", "diesel_l_saved", "tco2e_saved", "annual_saving_inr", "capex_inr")}
    totals["tco2e_saved"] = round(totals["tco2e_saved"], 1)
    totals["payback_years"] = (round(totals["capex_inr"] / totals["annual_saving_inr"], 1)
                               if totals["annual_saving_inr"] > 0 else None)
    totals["electricity_reduction_pct"] = round(totals["kwh_saved"] / annual_kwh * 100, 1) if annual_kwh else 0
    return {
        "inputs": p,
        "baseline": {"annual_grid_kwh": round(annual_kwh), "annual_grid_tco2e": round(annual_kwh * grid / 1000, 1),
                     "grid_factor": grid, "tariff": settings.electricity_tariff},
        "measures": measures,
        "totals": totals,
    }
