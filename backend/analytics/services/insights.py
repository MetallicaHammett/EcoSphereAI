"""Dashboard read models: KPIs, module views, benchmarking, leaderboards and data quality."""

from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg, Count, Max, Sum
from django.utils import timezone

from accounts.models import User
from monitoring.models import Alert, Building, CampusSettings, EnvReading, Meter, Reading, WeatherReading
from sustainability.models import CommuteSurvey, FuelLog, ReductionTarget, Tree, WasteLog

from .carbon import CATEGORY_LABELS, FactorBook, commute_daily_km_by_mode, emission_items, group, scope_split
from .common import (DateRange, daily_totals, data_days, day_start, hourly_totals, non_working_days, r, readings,
                     safe_div)


def _buildings():
    return {b.id: b for b in Building.objects.all()}


def _sum(qs):
    return qs.aggregate(t=Sum("value"))["t"] or 0.0


def _peak(qs):
    peak = max(hourly_totals(qs), key=lambda row: row["total"], default=None)
    if not peak:
        return None
    return {"kw": r(peak["total"], 0), "at": timezone.localtime(peak["hour"]).isoformat()}


# ---------------------------------------------------------------- overview

def overview(rng):
    settings = CampusSettings.load()
    book = FactorBook()
    buildings = _buildings()
    items = emission_items(rng, book=book)
    total_kg = sum(i.kg for i in items)

    grid_qs = readings(Meter.Kind.ELECTRICITY, rng)
    days = data_days(grid_qs) or rng.days
    annualise = 365 / days
    grid_kwh = _sum(grid_qs)
    solar_kwh = _sum(readings(Meter.Kind.SOLAR, rng))
    area = sum(b.area_m2 for b in buildings.values())
    water_kl = _sum(readings(Meter.Kind.WATER, rng))
    sources = {row["meter__source"]: row["t"] for row in readings(Meter.Kind.WATER_SOURCE, rng)
               .values("meter__source").annotate(t=Sum("value"))}
    supply = sum(sources.values())
    waste = WasteLog.objects.filter(date__gte=rng.start, date__lt=rng.end)
    waste_kg = waste.aggregate(t=Sum("weight_kg"))["t"] or 0
    diverted_kg = waste.filter(disposal__in=WasteLog.DIVERTED).aggregate(t=Sum("weight_kg"))["t"] or 0
    wet = waste.filter(category=WasteLog.Category.WET)
    wet_kg = wet.aggregate(t=Sum("weight_kg"))["t"] or 0
    wet_treated = wet.filter(disposal__in=[WasteLog.Disposal.COMPOSTED, WasteLog.Disposal.BIOGAS]) \
        .aggregate(t=Sum("weight_kg"))["t"] or 0
    surveys = CommuteSurvey.objects.count()
    sustainable = CommuteSurvey.objects.filter(mode__in=CommuteSurvey.SUSTAINABLE).count()
    sequestration_t = sum(t.count * t.sequestration_kg_per_tree for t in Tree.objects.all()) / 1000

    scopes = scope_split(items)
    market_scope2 = scopes["scope2"] * (1 - settings.green_power_share)
    annual_t = total_kg / 1000 * annualise
    target = ReductionTarget.objects.filter(target_year__gte=timezone.localdate().year).first()
    target_info = None
    if target:
        reduction = safe_div(target.baseline_tco2e - annual_t, target.baseline_tco2e) * 100
        target_info = {
            "name": target.name, "baseline_year": target.baseline_year, "baseline_tco2e": r(target.baseline_tco2e, 0),
            "target_year": target.target_year, "target_tco2e": r(target.target_tco2e, 0),
            "reduction_pct_required": target.reduction_pct, "reduction_achieved_pct": r(reduction, 1),
            "progress_pct": r(max(0.0, min(100.0, safe_div(reduction, target.reduction_pct) * 100)), 0),
        }

    monthly = defaultdict(lambda: {"scope1": 0.0, "scope2": 0.0, "scope3": 0.0})
    for item in items:
        monthly[item.day.strftime("%Y-%m")][f"scope{item.scope}"] += item.kg / 1000
    by_building = group([i for i in items if i.building_id], lambda i: i.building_id)
    open_alerts = Alert.objects.exclude(status=Alert.Status.RESOLVED)

    return {
        "range": {"start": rng.start, "end": rng.end - timedelta(days=1), "days": rng.days, "data_days": days},
        "campus": {"name": settings.name, "students": settings.student_count, "staff": settings.staff_count,
                   "area_m2": area, "buildings": len(buildings)},
        "carbon": {
            "total_tco2e": r(total_kg / 1000, 1),
            "annualised_tco2e": r(annual_t, 0),
            "per_student_t": r(safe_div(annual_t, settings.student_count), 3),
            "per_m2_kg": r(safe_div(annual_t * 1000, area), 1),
            "scope1_t": r(scopes["scope1"] / 1000, 1), "scope2_t": r(scopes["scope2"] / 1000, 1),
            "scope3_t": r(scopes["scope3"] / 1000, 1),
            "scope2_market_t": r(market_scope2 / 1000, 1),
            "sequestration_t_per_year": r(sequestration_t, 1),
            "grid_factor": book.value("electricity_grid"),
        },
        "by_category": sorted([{"category": CATEGORY_LABELS.get(k, k), "key": k, "tco2e": r(v / 1000, 2)}
                               for k, v in group(items, lambda i: i.category).items()], key=lambda x: -x["tco2e"]),
        "by_building": sorted([{"building": buildings[k].name, "tco2e": r(v / 1000, 2)}
                               for k, v in by_building.items() if k in buildings], key=lambda x: -x["tco2e"]),
        "monthly": [{"month": m, **{k: r(v, 2) for k, v in s.items()}} for m, s in sorted(monthly.items())],
        "energy": {
            "grid_kwh": r(grid_kwh, 0), "solar_kwh": r(solar_kwh, 0),
            "renewable_share_pct": r(safe_div(solar_kwh, grid_kwh + solar_kwh) * 100, 1),
            "eui_kwh_m2_yr": r(safe_div((grid_kwh + solar_kwh) * annualise, area), 1),
            "peak_demand": _peak(grid_qs),
            "cost_inr": r(grid_kwh * settings.electricity_tariff, 0),
        },
        "water": {
            "consumption_kl": r(water_kl, 0),
            "litres_per_person_day": r(safe_div(water_kl * 1000, settings.population * days), 1),
            "recycled_harvested_pct": r(safe_div(sources.get("recycled", 0) + sources.get("rainwater", 0), supply) * 100, 1),
            "cost_inr": r(water_kl * settings.water_tariff, 0),
        },
        "waste": {
            "total_kg": r(waste_kg, 0),
            "per_person_day_kg": r(safe_div(waste_kg, settings.population * days), 3),
            "diversion_rate_pct": r(safe_div(diverted_kg, waste_kg) * 100, 1),
            "organic_treated_pct": r(safe_div(wet_treated, wet_kg) * 100, 1),
        },
        "transport": {
            "survey_responses": surveys,
            "sustainable_share_pct": r(safe_div(sustainable, surveys) * 100, 1),
            "fleet_diesel_l": r(FuelLog.objects.filter(category=FuelLog.Category.FLEET, date__gte=rng.start,
                                                       date__lt=rng.end).aggregate(t=Sum("quantity"))["t"], 0),
        },
        "target": target_info,
        "alerts": {
            "open": open_alerts.count(),
            "critical": open_alerts.filter(severity__in=[Alert.Severity.HIGH, Alert.Severity.CRITICAL]).count(),
            "recent": [{"id": a.id, "title": a.title, "severity": a.severity, "status": a.status,
                        "category": a.category, "occurred_on": a.occurred_on}
                       for a in open_alerts.order_by("-created_at")[:6]],
        },
        "engagement": {
            "active_users_30d": User.objects.filter(last_login__gte=timezone.now() - timedelta(days=30)).count(),
            "registered_users": User.objects.count(),
        },
    }


# ---------------------------------------------------------------- energy

def energy(rng, building_id=None, granularity="day"):
    settings = CampusSettings.load()
    buildings = _buildings()
    if granularity == "hour" and rng.days > 14:
        granularity = "day"
    grid_qs = readings(Meter.Kind.ELECTRICITY, rng, building_id=building_id)
    solar_qs = readings(Meter.Kind.SOLAR, rng, building_id=building_id)

    series = defaultdict(lambda: {"grid": 0.0, "solar": 0.0})
    agg = hourly_totals if granularity == "hour" else daily_totals
    key = "hour" if granularity == "hour" else "day"
    for name, qs in (("grid", grid_qs), ("solar", solar_qs)):
        for row in agg(qs):
            stamp = timezone.localtime(row[key]).isoformat() if key == "hour" else row[key].isoformat()
            series[stamp][name] += row["total"]

    per_building = defaultdict(lambda: {"grid": 0.0, "solar": 0.0})
    for name, qs in (("grid", grid_qs), ("solar", solar_qs)):
        for row in qs.values("meter__building_id").annotate(t=Sum("value")):
            per_building[row["meter__building_id"]][name] += row["t"]

    days = data_days(grid_qs) or 1
    off_days = non_working_days(rng.start, rng.end)
    after_hours = total_non_res = 0.0
    for row in hourly_totals(grid_qs.exclude(meter__building__type=Building.Type.HOSTEL)):
        hour = timezone.localtime(row["hour"])
        total_non_res += row["total"]
        if hour.hour >= 20 or hour.hour < 7 or hour.date() in off_days:
            after_hours += row["total"]

    by_type = defaultdict(float)
    rows = []
    for bid, v in per_building.items():
        b = buildings.get(bid)
        if not b:
            continue
        load = v["grid"] + v["solar"]
        by_type[b.get_type_display()] += load
        rows.append({"id": bid, "building": b.name, "type": b.get_type_display(), "grid_kwh": r(v["grid"], 0),
                     "solar_kwh": r(v["solar"], 0), "kwh_per_m2_yr": r(load * 365 / days / b.area_m2, 1)})
    grid_kwh = _sum(grid_qs)
    solar_kwh = _sum(solar_qs)
    return {
        "granularity": granularity,
        "series": [{"t": t, "grid": r(v["grid"], 1), "solar": r(v["solar"], 1), "total": r(v["grid"] + v["solar"], 1)}
                   for t, v in sorted(series.items())],
        "buildings": sorted(rows, key=lambda x: -(x["grid_kwh"] + x["solar_kwh"])),
        "by_type": [{"type": k, "kwh": r(v, 0)} for k, v in sorted(by_type.items(), key=lambda x: -x[1])],
        "totals": {
            "grid_kwh": r(grid_kwh, 0), "solar_kwh": r(solar_kwh, 0),
            "renewable_share_pct": r(safe_div(solar_kwh, grid_kwh + solar_kwh) * 100, 1),
            "cost_inr": r(grid_kwh * settings.electricity_tariff, 0),
            "tco2e": r(grid_kwh * FactorBook().value("electricity_grid") / 1000, 1),
            "after_hours_share_pct": r(safe_div(after_hours, total_non_res) * 100, 1),
            "peak_demand": _peak(grid_qs),
        },
    }


# ---------------------------------------------------------------- live operations

def live():
    now = timezone.now()
    buildings = _buildings()
    meters = list(Meter.objects.filter(is_active=True))
    latest = {}
    recent = Reading.objects.filter(timestamp__gte=now - timedelta(hours=3)).order_by("meter_id", "-timestamp")
    for row in recent.values("meter_id", "value", "interval_minutes", "timestamp"):
        latest.setdefault(row["meter_id"], row)

    status = defaultdict(lambda: {"grid_kw": 0.0, "solar_kw": 0.0, "water_klph": 0.0})
    for meter in meters:
        row = latest.get(meter.id)
        if not row or meter.building_id is None:
            continue
        rate = row["value"] * 60 / max(row["interval_minutes"], 1)
        field = {"electricity": "grid_kw", "solar": "solar_kw", "water": "water_klph"}.get(meter.kind)
        if field:
            status[meter.building_id][field] += rate

    env = {}
    for row in EnvReading.objects.filter(timestamp__gte=now - timedelta(hours=3)).order_by("building_id", "-timestamp"):
        env.setdefault(row.building_id, row)
    open_alerts = defaultdict(int)
    for bid in Alert.objects.exclude(status=Alert.Status.RESOLVED).values_list("building_id", flat=True):
        open_alerts[bid] += 1

    rows = []
    for bid, b in buildings.items():
        s = status[bid]
        e = env.get(bid)
        rows.append({
            "id": bid, "building": b.name, "type": b.type, "type_label": b.get_type_display(),
            "latitude": b.latitude, "longitude": b.longitude,
            "grid_kw": r(s["grid_kw"], 1), "solar_kw": r(s["solar_kw"], 1), "water_klph": r(s["water_klph"], 2),
            "kw_per_100m2": r(s["grid_kw"] / b.area_m2 * 100, 2),
            "temperature": r(e.temperature, 1) if e else None, "humidity": r(e.humidity, 0) if e else None,
            "co2_ppm": r(e.co2_ppm, 0) if e else None, "occupancy": e.occupancy if e else None,
            "open_alerts": open_alerts.get(bid, 0),
        })
    weather = WeatherReading.objects.order_by("-timestamp").first()
    online = sum(1 for m in meters if m.last_reading_at and now - m.last_reading_at < timedelta(hours=2))
    newest = max((row["timestamp"] for row in latest.values()), default=None)
    return {
        "updated_at": newest,
        "buildings": rows,
        "totals": {k: r(sum(x[k] for x in rows), 1) for k in ("grid_kw", "solar_kw", "water_klph")},
        "weather": {"temperature": weather.temperature, "humidity": weather.humidity,
                    "irradiance": weather.irradiance, "rainfall_mm": weather.rainfall_mm,
                    "at": weather.timestamp} if weather else None,
        "meters": {"online": online, "total": len(meters)},
    }


# ---------------------------------------------------------------- water

def water(rng):
    settings = CampusSettings.load()
    buildings = _buildings()
    cons_qs = readings(Meter.Kind.WATER, rng)
    days = data_days(cons_qs) or 1
    daily = defaultdict(float)
    for row in daily_totals(cons_qs):
        daily[row["day"].isoformat()] += row["total"]
    supply_daily = defaultdict(lambda: defaultdict(float))
    for row in daily_totals(readings(Meter.Kind.WATER_SOURCE, rng), "meter__source"):
        supply_daily[row["day"].isoformat()][row["meter__source"]] += row["total"]
    sources = defaultdict(float)
    for v in supply_daily.values():
        for s, kl in v.items():
            sources[s] += kl

    # Night-time minimum flow for the last 7 nights: continuous night flow means leaks.
    night_start = day_start(timezone.localdate() - timedelta(days=7))
    nights = defaultdict(lambda: defaultdict(list))
    for row in hourly_totals(readings(Meter.Kind.WATER, start=night_start), "meter__building_id"):
        hour = timezone.localtime(row["hour"])
        if 1 <= hour.hour <= 4:
            nights[row["meter__building_id"]][hour.date()].append(row["total"])

    leaking = set(Alert.objects.filter(alert_type="leak").exclude(status=Alert.Status.RESOLVED)
                  .values_list("building_id", flat=True))
    rows = []
    for row in cons_qs.values("meter__building_id").annotate(t=Sum("value")):
        b = buildings.get(row["meter__building_id"])
        if not b:
            continue
        night = nights.get(b.id, {})
        night_series = [{"date": d.isoformat(), "min_klph": r(min(v), 2)} for d, v in sorted(night.items()) if v]
        rows.append({"id": b.id, "building": b.name, "type": b.get_type_display(), "kl": r(row["t"], 1),
                     "litres_per_occupant_day": r(row["t"] * 1000 / max(b.occupants, 1) / days, 1),
                     "night_flow": night_series, "leak_alert": b.id in leaking,
                     "latest_night_min_klph": night_series[-1]["min_klph"] if night_series else None})
    total = sum(daily.values())
    supply = sum(sources.values())
    labels = dict(Meter.Source.choices)
    return {
        "daily": [{"date": d, "kl": r(v, 1), **{s: r(kl, 1) for s, kl in supply_daily.get(d, {}).items()}}
                  for d, v in sorted(daily.items())],
        "sources": [{"source": labels.get(s, s), "key": s, "kl": r(v, 0), "share_pct": r(safe_div(v, supply) * 100, 1)}
                    for s, v in sorted(sources.items(), key=lambda x: -x[1])],
        "buildings": sorted(rows, key=lambda x: -x["kl"]),
        "totals": {
            "consumption_kl": r(total, 0),
            "litres_per_person_day": r(safe_div(total * 1000, settings.population * days), 1),
            "recycled_harvested_pct": r(safe_div(sources.get("recycled", 0) + sources.get("rainwater", 0), supply) * 100, 1),
            "rainwater_kl": r(sources.get("rainwater", 0), 0),
            "recycled_kl": r(sources.get("recycled", 0), 0),
            "cost_inr": r(total * settings.water_tariff, 0),
            "tco2e": r(total * FactorBook().value("water_supply") / 1000, 2),
        },
    }


# ---------------------------------------------------------------- waste

def waste(rng):
    settings = CampusSettings.load()
    book = FactorBook()
    logs = WasteLog.objects.filter(date__gte=rng.start, date__lt=rng.end)
    cat_labels = dict(WasteLog.Category.choices)
    disp_labels = dict(WasteLog.Disposal.choices)
    weekly = defaultdict(lambda: defaultdict(float))
    by_cat = defaultdict(float)
    by_disp = defaultdict(float)
    avoided = emitted = 0.0
    landfill = book.value("waste_landfill")
    for log in logs:
        week = (log.date - timedelta(days=log.date.weekday())).isoformat()
        weekly[week][log.category] += log.weight_kg
        by_cat[log.category] += log.weight_kg
        by_disp[log.disposal] += log.weight_kg
        factor = book.value(f"waste_{log.disposal}", log.date)
        emitted += log.weight_kg * factor
        if log.disposal in WasteLog.DIVERTED:
            avoided += log.weight_kg * max(landfill - factor, 0)
    total = sum(by_cat.values())
    diverted = sum(v for k, v in by_disp.items() if k in WasteLog.DIVERTED)
    days = max(len({log.date for log in logs}), 1)
    wet_treated = logs.filter(category=WasteLog.Category.WET,
                              disposal__in=[WasteLog.Disposal.COMPOSTED, WasteLog.Disposal.BIOGAS]) \
        .aggregate(t=Sum("weight_kg"))["t"] or 0
    return {
        "weekly": [{"week": w, **{k: r(v, 0) for k, v in cats.items()}} for w, cats in sorted(weekly.items())],
        "by_category": [{"key": k, "category": cat_labels[k], "kg": r(v, 0)} for k, v in by_cat.items()],
        "by_disposal": [{"key": k, "disposal": disp_labels[k], "kg": r(v, 0)} for k, v in by_disp.items()],
        "totals": {
            "total_kg": r(total, 0),
            "diversion_rate_pct": r(safe_div(diverted, total) * 100, 1),
            "organic_treated_pct": r(safe_div(wet_treated, by_cat.get("wet", 0)) * 100, 1),
            "per_person_day_kg": r(safe_div(total, settings.population * days), 3),
            "emitted_tco2e": r(emitted / 1000, 2),
            "avoided_tco2e": r(avoided / 1000, 2),
            "ewaste_kg": r(by_cat.get("ewaste", 0), 1),
            "hazardous_kg": r(by_cat.get("hazardous", 0), 1),
        },
    }


# ---------------------------------------------------------------- transport

def transport(rng):
    book = FactorBook()
    fleet = FuelLog.objects.filter(category=FuelLog.Category.FLEET, date__gte=rng.start, date__lt=rng.end)
    vehicles = []
    for row in fleet.values("asset", "activity").annotate(litres=Sum("quantity"), km=Sum("distance_km")):
        kg = row["litres"] * book.value(row["activity"])
        vehicles.append({"asset": row["asset"] or "Unnamed", "fuel": row["activity"], "litres": r(row["litres"], 0),
                         "km": r(row["km"], 0), "km_per_litre": r(safe_div(row["km"] or 0, row["litres"]), 2),
                         "tco2e": r(kg / 1000, 2)})
    labels = dict(CommuteSurvey.Mode.choices)
    counts = {row["mode"]: row["n"] for row in CommuteSurvey.objects.values("mode").annotate(n=Count("id"))}
    responses = sum(counts.values())
    daily_km = commute_daily_km_by_mode()
    modes = []
    for mode, label in labels.items():
        km = daily_km.get(mode, 0)
        modes.append({"mode": mode, "label": label, "responses": counts.get(mode, 0),
                      "share_pct": r(safe_div(counts.get(mode, 0), responses) * 100, 1),
                      "annual_tco2e": r(km * 365 * book.value(f"commute_{mode}") / 1000, 1),
                      "sustainable": mode in CommuteSurvey.SUSTAINABLE})
    avg = CommuteSurvey.objects.aggregate(d=Avg("distance_km"))["d"] or 0
    return {
        "fleet": sorted(vehicles, key=lambda v: -v["litres"]),
        "modes": modes,
        "totals": {
            "fleet_litres": r(sum(v["litres"] for v in vehicles), 0),
            "fleet_km": r(sum(v["km"] for v in vehicles), 0),
            "fleet_tco2e": r(sum(v["tco2e"] for v in vehicles), 2),
            "commute_annual_tco2e": r(sum(m["annual_tco2e"] for m in modes), 0),
            "survey_responses": responses,
            "sustainable_share_pct": r(sum(m["share_pct"] for m in modes if m["sustainable"]), 1),
            "average_distance_km": r(avg, 1),
        },
    }


# ---------------------------------------------------------------- green cover

def green():
    trees = list(Tree.objects.all())
    seq = sum(t.count * t.sequestration_kg_per_tree for t in trees) / 1000
    canopy = sum(t.count * t.canopy_m2_per_tree for t in trees)
    today = timezone.localdate()
    rng = DateRange(today - timedelta(days=30), today)
    items = emission_items(rng)
    annual = sum(i.kg for i in items) / 1000 * 365 / max(rng.days, 1)
    return {
        "species": [{"id": t.id, "species": t.species, "zone": t.zone, "count": t.count,
                     "planted_year": t.planted_year, "tco2_per_year": r(t.count * t.sequestration_kg_per_tree / 1000, 2),
                     "canopy_m2": r(t.count * t.canopy_m2_per_tree, 0)} for t in trees],
        "totals": {"trees": sum(t.count for t in trees), "species": len(trees), "canopy_m2": r(canopy, 0),
                   "sequestration_tco2_per_year": r(seq, 1), "annual_emissions_tco2e": r(annual, 0),
                   "offset_pct": r(safe_div(seq, annual) * 100, 2)},
        "note": "Sequestration is a conservative estimate, reported separately and never netted against "
                "emissions; it is not a substitute for reducing them.",
    }


# ---------------------------------------------------------------- benchmarking & leaderboard

def benchmark(rng):
    buildings = _buildings()
    grid_qs = readings(Meter.Kind.ELECTRICITY, rng)
    days = data_days(grid_qs) or 1
    energy_kwh = defaultdict(float)
    for qs in (grid_qs, readings(Meter.Kind.SOLAR, rng)):
        for row in qs.values("meter__building_id").annotate(t=Sum("value")):
            energy_kwh[row["meter__building_id"]] += row["t"]
    grid = {row["meter__building_id"]: row["t"] for row in grid_qs.values("meter__building_id").annotate(t=Sum("value"))}
    water_kl = {row["meter__building_id"]: row["t"] for row in readings(Meter.Kind.WATER, rng)
                .values("meter__building_id").annotate(t=Sum("value"))}
    factor = FactorBook().value("electricity_grid")
    rows = []
    for b in buildings.values():
        kwh = energy_kwh.get(b.id, 0)
        eui = kwh * 365 / days / b.area_m2
        stars = 5 if eui <= 75 else 4 if eui <= 100 else 3 if eui <= 140 else 2 if eui <= 190 else 1
        rows.append({"id": b.id, "building": b.name, "type": b.get_type_display(), "area_m2": b.area_m2,
                     "occupants": b.occupants, "eui_kwh_m2_yr": r(eui, 1),
                     "kwh_per_occupant_day": r(kwh / max(b.occupants, 1) / days, 2),
                     "water_l_per_occupant_day": r(water_kl.get(b.id, 0) * 1000 / max(b.occupants, 1) / days, 1),
                     "tco2e": r(grid.get(b.id, 0) * factor / 1000, 1), "stars": stars})
    rows.sort(key=lambda x: x["eui_kwh_m2_yr"])
    for i, row in enumerate(rows, 1):
        row["rank"] = i
    return {"buildings": rows, "days": days,
            "note": "Energy Performance Index (kWh/m2/year) annualised from the selected period. Star bands are "
                    "indicative, modelled on BEE building star-rating ranges."}


def leaderboard():
    """Energy-saving competition: this week's use per occupant vs the previous four weeks."""
    today = timezone.localdate()
    this_start, prev_start = today - timedelta(days=7), today - timedelta(days=35)
    rows = []
    for b in Building.objects.filter(type__in=[Building.Type.HOSTEL, Building.Type.ACADEMIC, Building.Type.LAB,
                                               Building.Type.LIBRARY]):
        qs = readings(Meter.Kind.ELECTRICITY, building_id=b.id)
        this = _sum(qs.filter(timestamp__gte=day_start(this_start), timestamp__lt=day_start(today)))
        prev = _sum(qs.filter(timestamp__gte=day_start(prev_start), timestamp__lt=day_start(this_start)))
        this_d = data_days(qs.filter(timestamp__gte=day_start(this_start), timestamp__lt=day_start(today))) or 1
        prev_d = data_days(qs.filter(timestamp__gte=day_start(prev_start), timestamp__lt=day_start(this_start))) or 1
        now_rate = this / this_d / max(b.occupants, 1)
        before = prev / prev_d / max(b.occupants, 1)
        change = safe_div(now_rate - before, before) * 100
        rows.append({"id": b.id, "building": b.name, "type": b.type, "type_label": b.get_type_display(),
                     "kwh_per_occupant_day": r(now_rate, 2), "previous": r(before, 2), "change_pct": r(change, 1),
                     "points": max(0, round(-change * 10)) + 50})
    rows.sort(key=lambda x: x["change_pct"])
    hostels = [x for x in rows if x["type"] == Building.Type.HOSTEL]
    departments = [x for x in rows if x["type"] != Building.Type.HOSTEL]
    for group_rows in (hostels, departments):
        for i, row in enumerate(group_rows, 1):
            row["rank"] = i
    return {"hostels": hostels, "departments": departments,
            "period": {"this_week_start": this_start, "baseline_start": prev_start}}


# ---------------------------------------------------------------- data quality

def data_quality():
    now = timezone.now()
    meters = list(Meter.objects.filter(is_active=True).select_related("building"))
    week_start = now - timedelta(days=7)
    hours = defaultdict(set)
    for row in hourly_totals(Reading.objects.filter(timestamp__gte=week_start), "meter_id"):
        hours[row["meter_id"]].add(row["hour"])
    expected = 7 * 24
    rows = []
    for m in meters:
        reporting = bool(m.last_reading_at and now - m.last_reading_at < timedelta(hours=2))
        rows.append({"id": m.id, "meter": m.name, "serial": m.serial, "kind": m.get_kind_display(),
                     "building": m.building.name if m.building else "-", "reporting": reporting,
                     "last_reading_at": m.last_reading_at,
                     "completeness_pct": r(min(len(hours.get(m.id, ())) / expected, 1) * 100, 1)})
    suspect = Reading.objects.filter(timestamp__gte=week_start, quality=Reading.Quality.SUSPECT).count()
    resolved = Alert.objects.filter(resolved_at__isnull=False, resolved_at__gte=now - timedelta(days=30))
    durations = [(a.resolved_at - a.created_at).total_seconds() / 3600 for a in resolved]
    return {
        "meters": rows,
        "totals": {
            "reporting_pct": r(safe_div(sum(1 for x in rows if x["reporting"]), len(rows)) * 100, 1),
            "completeness_pct": r(safe_div(sum(x["completeness_pct"] for x in rows), len(rows)), 1),
            "suspect_readings_7d": suspect,
            "mean_hours_to_resolve": r(safe_div(sum(durations), len(durations)), 1) if durations else None,
            "latest_reading": Reading.objects.aggregate(t=Max("timestamp"))["t"],
        },
    }
