"""
Creates a complete demo campus: buildings, meters, emission factors, users and N days of
hourly history with a few realistic faults injected for the anomaly detector to find.

    python manage.py seed_demo            # 120 days
    python manage.py seed_demo --days 60 --reset
"""

import random
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from analytics import simulation as sim
from analytics.services import anomaly
from analytics.services.carbon import emission_items
from analytics.services.common import DateRange, non_working_days
from monitoring.models import (Alert, Building, CalendarDay, CampusSettings, EnvReading, Gateway, Meter, Reading,
                               WeatherReading)
from sustainability.models import CommuteSurvey, EmissionFactor, FuelLog, ReductionTarget, Tree, WasteLog

FACTORS = [
    # activity, scope, value, unit, valid_from, source
    ("electricity_grid", 2, 0.757, "kWh", date(2023, 4, 1),
     "CEA CO2 Baseline Database for the Indian Power Sector, earlier edition (approx.; verify)"),
    ("electricity_grid", 2, 0.716, "kWh", date(2025, 4, 1),
     "CEA CO2 Baseline Database, recent weighted average (approx.; confirm latest official value)"),
    ("diesel", 1, 2.68, "L", date(2020, 1, 1), "IPCC 2006 Guidelines / DEFRA conversion factors"),
    ("petrol", 1, 2.31, "L", date(2020, 1, 1), "IPCC 2006 Guidelines / DEFRA conversion factors"),
    ("lpg", 1, 2.98, "kg", date(2020, 1, 1), "IPCC 2006 Guidelines"),
    ("refrigerant_r410a", 1, 2088, "kg", date(2020, 1, 1), "IPCC AR4 100-year GWP"),
    ("refrigerant_r32", 1, 675, "kg", date(2020, 1, 1), "IPCC AR4 100-year GWP"),
    ("refrigerant_r22", 1, 1810, "kg", date(2020, 1, 1), "IPCC AR4 100-year GWP"),
    ("water_supply", 3, 0.344, "kL", date(2020, 1, 1), "DEFRA water supply + treatment (indicative)"),
    ("waste_landfill", 3, 0.497, "kg", date(2020, 1, 1), "DEFRA mixed municipal waste to landfill (indicative)"),
    ("waste_recycled", 3, 0.021, "kg", date(2020, 1, 1), "DEFRA closed-loop recycling (indicative)"),
    ("waste_composted", 3, 0.009, "kg", date(2020, 1, 1), "DEFRA composting (indicative)"),
    ("waste_biogas", 3, 0.009, "kg", date(2020, 1, 1), "DEFRA anaerobic digestion (indicative)"),
    ("waste_incinerated", 3, 0.021, "kg", date(2020, 1, 1), "DEFRA combustion (indicative)"),
    ("commute_car", 3, 0.171, "km", date(2020, 1, 1), "DEFRA average car per passenger-km"),
    ("commute_two_wheeler", 3, 0.083, "km", date(2020, 1, 1), "DEFRA small motorbike"),
    ("commute_bus", 3, 0.105, "km", date(2020, 1, 1), "DEFRA local bus per passenger-km"),
    ("commute_auto", 3, 0.100, "km", date(2020, 1, 1), "Indicative CNG/LPG three-wheeler"),
    ("commute_train", 3, 0.035, "km", date(2020, 1, 1), "Indicative metro / suburban rail"),
    ("commute_ev", 3, 0.025, "km", date(2020, 1, 1), "Electric two-wheeler at Indian grid intensity"),
    ("commute_walk", 3, 0.0, "km", date(2020, 1, 1), "Zero emission"),
    ("commute_cycle", 3, 0.0, "km", date(2020, 1, 1), "Zero emission"),
]

HOLIDAYS = [(1, 1, "New Year"), (1, 14, "Pongal"), (1, 15, "Thiruvalluvar Day"), (1, 26, "Republic Day"),
            (5, 1, "May Day"), (8, 15, "Independence Day"), (10, 2, "Gandhi Jayanti"), (12, 25, "Christmas")]

TREES = [("Neem", "Main avenue", 320, 25, 30), ("Rain tree", "Central lawn", 85, 45, 120),
         ("Coconut", "Hostel zone", 210, 10, 15), ("Mango", "Staff quarters", 60, 30, 40),
         ("Gulmohar", "Library lawn", 75, 22, 50), ("Banyan", "Heritage garden", 12, 60, 250),
         ("Peepal", "Heritage garden", 18, 50, 200), ("Ashoka", "Boundary wall", 150, 8, 6)]

COMMUTE = [("walk", 12, 0.4, 2), ("cycle", 4, 1, 5), ("bus", 30, 5, 20), ("train", 14, 5, 25),
           ("two_wheeler", 22, 3, 18), ("ev", 4, 3, 15), ("auto", 6, 2, 10), ("car", 8, 5, 25)]


class Command(BaseCommand):
    help = "Seed a realistic demo campus with history and injected faults."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=120)
        parser.add_argument("--reset", action="store_true", help="Delete existing campus data first")

    def handle(self, *args, **opts):
        days = max(30, min(opts["days"], 400))
        if opts["reset"]:
            self.stdout.write("Removing existing data...")
            for model in (Alert, Reading, EnvReading, WeatherReading, Meter, Gateway, Building, CalendarDay,
                          FuelLog, WasteLog, CommuteSurvey, Tree, ReductionTarget, EmissionFactor):
                model.objects.all().delete()
        elif Building.objects.exists():
            self.stdout.write(self.style.WARNING("Data already exists. Use --reset to rebuild it."))
            return

        now = timezone.localtime()
        end = now.replace(minute=0, second=0, microsecond=0)
        start = (end - timedelta(days=days)).replace(hour=0)
        rnd = random.Random(42)

        with transaction.atomic():
            self._reference(now.date(), start.date())
            buildings, meters, gateway = self._campus()
            self._users()
        self.stdout.write(f"Generating {days} days of hourly data for {len(meters)} meters...")
        self._history(buildings, meters, start, end, rnd)
        with transaction.atomic():
            self._logs(start.date(), end.date(), buildings, rnd)
            self._commutes_and_trees(rnd)
            self._target(end.date())
        Meter.objects.update(last_reading_at=end - timedelta(hours=1) + timedelta(minutes=59))
        Gateway.objects.update(last_seen=timezone.now())
        result = anomaly.scan(now)
        self.stdout.write(self.style.SUCCESS(
            f"Done. {Reading.objects.count():,} readings, {result['created']} alerts raised.\n"
            f"Gateway key for the simulator / devices: {gateway.key}\n"
            "Demo logins: admin / admin123, facility / facility123, student / student123"))

    # ------------------------------------------------------------------ reference data
    def _reference(self, today, start):
        CampusSettings.load().save()
        for activity, scope, value, unit, valid_from, source in FACTORS:
            version = EmissionFactor.objects.filter(activity=activity).count() + 1
            EmissionFactor.objects.create(activity=activity, scope=scope, value=value, activity_unit=unit,
                                          valid_from=valid_from, source=source, version=version)
        for year in (today.year - 1, today.year, today.year + 1):
            for month, day, label in HOLIDAYS:
                CalendarDay.objects.get_or_create(date=date(year, month, day),
                                                  defaults={"kind": CalendarDay.Kind.HOLIDAY, "label": label})
        if today.year == 2026:
            CalendarDay.objects.get_or_create(date=date(2026, 11, 8), defaults={"kind": "holiday", "label": "Deepavali"})
        for offset in range(44, 51):
            d = today - timedelta(days=offset)
            if d >= start:
                CalendarDay.objects.get_or_create(date=d, defaults={"kind": CalendarDay.Kind.VACATION,
                                                                    "label": "Mid-semester break"})

    def _campus(self):
        gateway = Gateway.objects.create(name="Main campus LoRaWAN / Wi-Fi gateway")
        buildings, meters = {}, []
        for code, name, btype, area, occ, lat, lng, kwp, _ in sim.BUILDINGS:
            b = Building.objects.create(code=code, name=name, type=btype, area_m2=area, occupants=occ,
                                        latitude=lat, longitude=lng)
            buildings[code] = b
            peak = sim.building_load_kw(btype, area, datetime(2026, 5, 1, 14), True, 38)
            meters.append(Meter.objects.create(building=b, gateway=gateway, name=f"{name} - main incomer",
                                               serial=f"EM-{code}", kind=Meter.Kind.ELECTRICITY, unit="kWh",
                                               max_value=round(peak * 3)))
            if kwp:
                meters.append(Meter.objects.create(building=b, gateway=gateway, name=f"{name} - rooftop solar",
                                                   serial=f"SM-{code}", kind=Meter.Kind.SOLAR, unit="kWh",
                                                   capacity=kwp, max_value=kwp * 1.2))
            meters.append(Meter.objects.create(building=b, gateway=gateway, name=f"{name} - water",
                                               serial=f"WM-{code}", kind=Meter.Kind.WATER, unit="kL",
                                               max_value=max(occ * 0.06, 10)))
        for source, label in Meter.Source.choices:
            if source:
                meters.append(Meter.objects.create(gateway=gateway, name=label, serial=f"WS-{source.upper()}",
                                                   kind=Meter.Kind.WATER_SOURCE, source=source, unit="kL",
                                                   max_value=500))
        return buildings, meters, gateway

    def _users(self):
        for username, password, role, dept in (("admin", "admin123", User.Role.ADMIN, "Sustainability Office"),
                                               ("facility", "facility123", User.Role.FACILITY, "Estate Office"),
                                               ("student", "student123", User.Role.COMMUNITY, "CSE")):
            if not User.objects.filter(username=username).exists():
                user = User(username=username, role=role, department=dept, email=f"{username}@campus.local",
                            first_name=username.title(), is_staff=role == User.Role.ADMIN,
                            is_superuser=role == User.Role.ADMIN)
                user.set_password(password)
                user.save()

    # ------------------------------------------------------------------ time series
    def _history(self, buildings, meters, start, end, rnd):
        by_serial = {m.serial: m for m in meters}
        off_days = non_working_days(start.date(), end.date() + timedelta(days=1))
        today = end.date()
        readings, env, weather_rows = [], [], []

        def flush(force=False):
            if len(readings) >= 20000 or force:
                Reading.objects.bulk_create(readings, batch_size=5000)
                readings.clear()
            if len(env) >= 5000 or force:
                EnvReading.objects.bulk_create(env, batch_size=5000)
                env.clear()

        ts = start
        while ts < end:
            local = timezone.localtime(ts)
            working = local.date() not in off_days
            w = sim.weather(local)
            weather_rows.append(WeatherReading(timestamp=ts, temperature=w.temperature, humidity=w.humidity,
                                               irradiance=w.irradiance, rainfall_mm=w.rainfall_mm))
            age_days = (today - local.date()).days
            total_water = 0.0
            for code, name, btype, area, occ, *_rest in sim.BUILDINGS:
                kwp, has_env = _rest[2], _rest[3]
                load = sim.building_load_kw(btype, area, local, working, w.temperature, rnd.uniform(0.93, 1.07))
                # Injected faults the anomaly detector should find.
                night_of = (local - timedelta(hours=6)).date()
                if code == "ACB" and (local.hour >= 22 or local.hour < 6) and night_of >= today - timedelta(days=2):
                    load += 160  # air-conditioning left running overnight
                if code == "TPL" and age_days == 1 and 14 <= local.hour < 17:
                    load += 260  # test rig left on full power
                gen = sim.solar_kw(kwp, w.irradiance, rnd.uniform(0.9, 1.05)) if kwp else 0.0
                readings.append(Reading(meter=by_serial[f"EM-{code}"], timestamp=ts, value=round(max(load - gen, 0), 2)))
                if kwp:
                    readings.append(Reading(meter=by_serial[f"SM-{code}"], timestamp=ts, value=round(gen, 2)))
                water = sim.water_klph(btype, occ, local.hour, working, rnd.uniform(0.85, 1.15))
                if code == "BH1" and age_days <= 2:
                    water += 2.4  # leaking overhead-tank float valve
                total_water += water
                readings.append(Reading(meter=by_serial[f"WM-{code}"], timestamp=ts, value=round(water, 3)))
                if has_env:
                    t, h, co2, people = sim.indoor(btype, occ, local, working, w.temperature, rnd)
                    if code == "LIB" and age_days == 1 and 15 <= local.hour < 18:
                        co2, people = 1380 + rnd.randint(0, 120), int(occ * 0.9)  # packed hall, fresh air off
                    env.append(EnvReading(building=buildings[code], timestamp=ts, temperature=t, humidity=h,
                                          co2_ppm=co2, occupancy=people))
            for source, share in sim.SOURCE_SHARES.items():
                readings.append(Reading(meter=by_serial[f"WS-{source.upper()}"], timestamp=ts,
                                        value=round(total_water * 1.04 * share, 3)))
            flush()
            ts += timedelta(hours=1)
        flush(force=True)
        WeatherReading.objects.bulk_create(weather_rows, batch_size=5000)
        # One impossible value so data-quality checks have something to flag (kept, not counted).
        Reading.objects.create(meter=by_serial["EM-ADM"], timestamp=end - timedelta(hours=30), value=99999,
                               quality=Reading.Quality.SUSPECT)

    # ------------------------------------------------------------------ logged activity data
    def _logs(self, start, end, buildings, rnd):
        off_days = non_working_days(start, end + timedelta(days=1))
        fuel, waste = [], []
        buses = [f"TN-09-BX-11{n:02d}" for n in range(1, 7)]
        total_days = (end - start).days
        d = start
        while d < end:
            working = d not in off_days
            progress = (d - start).days / max(total_days, 1)
            if working:
                for bus in buses:
                    km = rnd.uniform(105, 140)
                    fuel.append(FuelLog(date=d, category="fleet", activity="diesel", asset=bus, distance_km=round(km, 1),
                                        quantity=round(km / rnd.uniform(3.7, 4.3), 1)))
                km = rnd.uniform(40, 80)
                fuel.append(FuelLog(date=d, category="fleet", activity="petrol", asset="TN-09-CA-2201 (staff car)",
                                    distance_km=round(km, 1), quantity=round(km / 12, 1)))
            fuel.append(FuelLog(date=d, category="canteen", activity="lpg", asset="Food court kitchen",
                                building=buildings["FDC"], quantity=round(rnd.uniform(55, 70) if working else 25, 1)))
            if rnd.random() < 0.07:
                fuel.append(FuelLog(date=d, category="generator", activity="diesel", asset="DG-1 (750 kVA)",
                                    quantity=round(rnd.uniform(120, 380)), notes="Grid outage backup"))
            scale = 1 if working else 0.45
            wet = rnd.uniform(650, 850) * scale
            for disposal, share in (("composted", 0.55), ("biogas", 0.25), ("landfill", 0.20)):
                waste.append(WasteLog(date=d, building=buildings["FDC"], category="wet", disposal=disposal,
                                      weight_kg=round(wet * share, 1)))
            dry = rnd.uniform(300, 400) * scale
            recycled_share = 0.25 + 0.15 * progress  # segregation drive is improving diversion
            waste.append(WasteLog(date=d, category="dry", disposal="recycled", weight_kg=round(dry * recycled_share, 1)))
            waste.append(WasteLog(date=d, category="dry", disposal="landfill", weight_kg=round(dry * (1 - recycled_share), 1)))
            waste.append(WasteLog(date=d, category="recyclable", disposal="recycled",
                                  weight_kg=round(rnd.uniform(150, 220) * scale, 1)))
            if d.weekday() == 0:
                waste.append(WasteLog(date=d, category="ewaste", disposal="recycled", weight_kg=round(rnd.uniform(20, 50), 1),
                                      notes="Authorised e-waste recycler"))
                waste.append(WasteLog(date=d, building=buildings["TPL"], category="hazardous", disposal="incinerated",
                                      weight_kg=round(rnd.uniform(5, 15), 1), notes="Lab chemical waste"))
            d += timedelta(days=1)
        fuel.append(FuelLog(date=end - timedelta(days=40), category="refrigerant", activity="refrigerant_r410a",
                            quantity=6, asset="Chiller CH-2", building=buildings["ACA"], notes="Leak repaired"))
        fuel.append(FuelLog(date=end - timedelta(days=80), category="refrigerant", activity="refrigerant_r32",
                            quantity=2.5, asset="Split ACs", building=buildings["BH1"], notes="Annual top-up"))
        FuelLog.objects.bulk_create(fuel)
        WasteLog.objects.bulk_create(waste)

    def _commutes_and_trees(self, rnd):
        surveys = []
        for mode, weight, lo, hi in COMMUTE:
            for _ in range(weight * 4):
                surveys.append(CommuteSurvey(mode=mode, distance_km=round(rnd.uniform(lo, hi), 1),
                                             days_per_week=rnd.choice([5, 5, 6]),
                                             respondent="student" if rnd.random() < 0.85 else "staff"))
        CommuteSurvey.objects.bulk_create(surveys)
        for species, zone, count, seq, canopy in TREES:
            Tree.objects.create(species=species, zone=zone, count=count, sequestration_kg_per_tree=seq,
                                canopy_m2_per_tree=canopy, planted_year=rnd.choice([1995, 2005, 2012, 2018]))

    def _target(self, today):
        rng = DateRange(today - timedelta(days=30), today)
        annual = sum(i.kg for i in emission_items(rng)) / 1000 * 365 / 30
        settings = CampusSettings.load()
        ReductionTarget.objects.create(name="Campus Climate Action Plan", baseline_year=settings.baseline_year,
                                       baseline_tco2e=round(annual * 1.07), target_year=2030, reduction_pct=45)
