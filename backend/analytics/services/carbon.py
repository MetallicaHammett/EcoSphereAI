"""
Carbon engine (GHG Protocol).

Emissions (kg CO2e) = activity data x emission factor, applied day by day so that a new
factor version only affects the days on or after its ``valid_from`` date.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Min
from django.utils import timezone

from monitoring.models import CampusSettings, Meter, Reading
from sustainability.models import CommuteSurvey, EmissionFactor, FuelLog, WasteLog

from .common import daily_totals, readings

ACADEMIC_WEEKS_PER_YEAR = 44
TREE_KG_PER_YEAR = 21.8  # widely used conservative figure for a mature tree

CATEGORY_LABELS = {
    "electricity": "Purchased electricity",
    "generator": "Diesel generators",
    "fleet": "Campus fleet",
    "canteen": "Canteen & labs (LPG)",
    "refrigerant": "Refrigerant leakage",
    "water": "Water supply & treatment",
    "waste": "Waste disposal",
    "commuting": "Student & staff commuting",
}


class FactorBook:
    """Loads every factor version once and answers 'which value applied on this day?'."""

    def __init__(self):
        self._rows = defaultdict(list)
        for factor in EmissionFactor.objects.order_by("valid_from"):
            self._rows[factor.activity].append(factor)

    def get(self, activity, on=None):
        rows = self._rows.get(activity)
        if not rows:
            return None
        on = on or timezone.localdate()
        chosen = rows[0]
        for factor in rows:
            if factor.valid_from <= on:
                chosen = factor
            else:
                break
        return chosen

    def value(self, activity, on=None):
        factor = self.get(activity, on)
        return factor.value if factor else 0.0

    def scope(self, activity, default):
        factor = self.get(activity)
        return factor.scope if factor else default


@dataclass
class Item:
    day: date
    scope: int
    category: str
    activity: str
    building_id: int | None
    quantity: float
    unit: str
    kg: float


def emission_items(rng, building_id=None, book=None):
    """Every emission line for the range; the basis for dashboards, reports and exports."""
    book = book or FactorBook()
    items = []

    def add(day, activity, category, building, quantity, unit, default_scope):
        factor = book.get(activity, day)
        if factor is None:
            return
        items.append(Item(day, factor.scope or default_scope, category, activity, building, quantity, unit,
                          quantity * factor.value))

    for row in daily_totals(readings(Meter.Kind.ELECTRICITY, rng, building_id=building_id), "meter__building_id"):
        add(row["day"], "electricity_grid", "electricity", row["meter__building_id"], row["total"], "kWh", 2)

    for row in daily_totals(readings(Meter.Kind.WATER, rng, building_id=building_id), "meter__building_id"):
        add(row["day"], "water_supply", "water", row["meter__building_id"], row["total"], "kL", 3)

    fuels = FuelLog.objects.filter(date__gte=rng.start, date__lt=rng.end)
    wastes = WasteLog.objects.filter(date__gte=rng.start, date__lt=rng.end)
    if building_id:
        fuels = fuels.filter(building_id=building_id)
        wastes = wastes.filter(building_id=building_id)
    for log in fuels:
        unit = "kg" if log.activity == "lpg" or log.activity.startswith("refrigerant") else "L"
        add(log.date, log.activity, log.category, log.building_id, log.quantity, unit, 1)
    for log in wastes:
        add(log.date, f"waste_{log.disposal}", "waste", log.building_id, log.weight_kg, "kg", 3)

    if not building_id:
        # Commuting is a modelled estimate; only count days the platform was actually monitoring.
        first = Reading.objects.aggregate(t=Min("timestamp"))["t"]
        today = timezone.localdate()
        daily_km = commute_daily_km_by_mode()
        day = max(rng.start, timezone.localtime(first).date()) if first else rng.end
        while day < rng.end and day <= today:
            for mode, km in daily_km.items():
                add(day, f"commute_{mode}", "commuting", None, km, "km", 3)
            day += timedelta(days=1)
    return items


def commute_daily_km_by_mode():
    """Survey responses scaled to the whole campus population (aggregated, never personal)."""
    surveys = list(CommuteSurvey.objects.values("mode", "distance_km", "days_per_week"))
    if not surveys:
        return {}
    population = CampusSettings.load().population
    km = defaultdict(float)
    for s in surveys:
        km[s["mode"]] += 2 * s["distance_km"] * s["days_per_week"] / 7
    # Spread the academic-year commute evenly over the calendar, matching commute_footprint().
    scale = population / len(surveys) * ACADEMIC_WEEKS_PER_YEAR / 52
    return {mode: total * scale for mode, total in km.items()}


def commute_footprint(mode, distance_km, days_per_week):
    book = FactorBook()
    annual_km = 2 * float(distance_km) * int(days_per_week) * ACADEMIC_WEEKS_PER_YEAR
    kg = annual_km * book.value(f"commute_{mode}")
    car_kg = annual_km * book.value("commute_car")
    bus_kg = annual_km * book.value("commute_bus")
    if mode in ("walk", "cycle"):
        tip = "Zero-emission commute - thank you! You are already a campus climate champion."
    elif kg > bus_kg * 1.2:
        tip = (f"Switching to the campus shuttle or public bus would save about "
               f"{round(kg - bus_kg)} kg CO2e a year.")
    else:
        tip = "Great choice. Car-pooling and combining trips can cut it even further."
    return {
        "annual_km": round(annual_km, 1),
        "annual_kg": round(kg, 1),
        "per_trip_kg": round(kg / max(int(days_per_week) * ACADEMIC_WEEKS_PER_YEAR * 2, 1), 3),
        "car_equivalent_kg": round(car_kg, 1),
        "saving_vs_car_kg": round(car_kg - kg, 1),
        "trees_to_offset": round(kg / TREE_KG_PER_YEAR, 1),
        "tip": tip,
    }


def group(items, key):
    totals = defaultdict(float)
    for item in items:
        totals[key(item)] += item.kg
    return totals


def scope_split(items):
    split = group(items, lambda i: i.scope)
    return {f"scope{s}": split.get(s, 0.0) for s in (1, 2, 3)}
