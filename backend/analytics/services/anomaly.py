"""
Anomaly and fault detection.

Each building's normal load profile is learnt as the median and MAD (median absolute
deviation) of the same hour on the same kind of day (working / non-working) over the
previous four weeks. Recent hours far above that profile raise alerts. Robust statistics
are used so that past anomalies do not distort the baseline.
"""

from collections import defaultdict
from datetime import timedelta
from statistics import median

from django.db import IntegrityError, transaction
from django.utils import timezone

from monitoring.models import Alert, Building, CampusSettings, EnvReading, Meter, Reading

from .common import hourly_by_meter, non_working_days

BASELINE_DAYS = 28
RECENT_HOURS = 48
Z_THRESHOLD = 4.0
NIGHT_HOURS = set(range(22, 24)) | set(range(0, 6))
LEAK_HOURS = (1, 2, 3, 4)
OFFLINE_AFTER = timedelta(hours=3)
CO2_LIMIT = 1200


def _severity(excess, thresholds):
    low, medium, high = thresholds
    if excess >= high:
        return Alert.Severity.CRITICAL
    if excess >= medium:
        return Alert.Severity.HIGH
    if excess >= low:
        return Alert.Severity.MEDIUM
    return Alert.Severity.LOW


def _raise(created, **fields):
    try:
        with transaction.atomic():
            _, made = Alert.objects.get_or_create(dedupe_key=fields.pop("dedupe_key"), defaults=fields)
    except IntegrityError:
        made = False
    if made:
        created.append(fields["title"])


def _operational_date(ts):
    """Hours after midnight belong to the previous evening's night."""
    return (ts - timedelta(days=1)).date() if ts.hour < 6 else ts.date()


def scan(now=None):
    now = timezone.localtime(now or timezone.now())
    end = now.replace(minute=0, second=0, microsecond=0)  # only complete hours
    recent_start = end - timedelta(hours=RECENT_HOURS)
    base_start = recent_start - timedelta(days=BASELINE_DAYS)
    off_days = non_working_days(base_start.date(), end.date() + timedelta(days=1))
    settings = CampusSettings.load()
    created = []

    _electricity(created, end, recent_start, base_start, off_days, settings)
    _water(created, end, settings)
    _stuck_and_suspect(created, now)
    _offline(created, now)
    _co2(created, now)
    return {"created": len(created), "titles": created, "scanned_at": now}


def _electricity(created, end, recent_start, base_start, off_days, settings):
    meters = list(Meter.objects.filter(kind=Meter.Kind.ELECTRICITY, is_active=True).select_related("building"))
    series = hourly_by_meter([m.id for m in meters], base_start, end)

    def day_kind(ts):
        return "off" if ts.date() in off_days else "on"

    for meter in meters:
        values = series.get(meter.id, {})
        buckets = defaultdict(list)
        for ts, v in values.items():
            if ts < recent_start:
                buckets[(day_kind(ts), ts.hour)].append(v)

        flagged = defaultdict(list)
        for ts, v in values.items():
            if ts < recent_start:
                continue
            history = buckets.get((day_kind(ts), ts.hour), [])
            if len(history) < 4:
                continue
            med = median(history)
            mad = median(abs(x - med) for x in history) * 1.4826
            scale = max(mad, 0.05 * med, 1.0)
            if (v - med) / scale > Z_THRESHOLD and v - med > max(0.2 * med, 25):
                night = ts.hour in NIGHT_HOURS
                flagged[(_operational_date(ts), night)].append((ts, v, med))

        building = meter.building
        for (day, night), hours in flagged.items():
            excess = sum(v - med for _, v, med in hours)
            after_hours = night and building is not None and not building.is_residential
            kind = "after_hours" if after_hours else "spike"
            first, last = min(h[0] for h in hours), max(h[0] for h in hours)
            name = building.name if building else meter.name
            if after_hours:
                title = f"{name}: high load outside working hours"
                message = (f"Consumption stayed {excess:,.0f} kWh above the normal night profile between "
                           f"{first:%d %b %H:00} and {(last + timedelta(hours=1)):%H:00}. Check air-conditioning, "
                           f"lighting and lab equipment left running.")
            else:
                title = f"{name}: unusual electricity spike"
                message = (f"{len(hours)} hour(s) on {day:%d %b} were well above the learnt profile "
                           f"(+{excess:,.0f} kWh). Peak {max(v for _, v, _ in hours):,.0f} kWh at "
                           f"{max(hours, key=lambda h: h[1])[0]:%H:00}.")
            _raise(created, dedupe_key=f"{kind}:{meter.id}:{day}", building=building, meter=meter,
                   category=Alert.Category.ENERGY, alert_type=kind,
                   severity=_severity(excess, (150, 500, 1500)), title=title, message=message,
                   excess_quantity=round(excess, 1), excess_unit="kWh",
                   estimated_cost=round(excess * settings.electricity_tariff), occurred_on=day)


def _water(created, end, settings):
    meters = list(Meter.objects.filter(kind=Meter.Kind.WATER, is_active=True).select_related("building"))
    start = end - timedelta(days=BASELINE_DAYS + 4)
    series = hourly_by_meter([m.id for m in meters], start, end)
    today = end.date()
    for meter in meters:
        nights = defaultdict(list)
        for ts, v in series.get(meter.id, {}).items():
            if ts.hour in LEAK_HOURS:
                nights[ts.date()].append(v)
        night_min = {d: min(v) for d, v in nights.items() if len(v) >= 3}
        recent = [d for d in night_min if d >= today - timedelta(days=3)]
        history = [v for d, v in night_min.items() if d < today - timedelta(days=3)]
        if len(history) < 7:
            continue
        baseline = median(history)
        # A leak is one continuing problem: keep a single open work order per meter.
        if Alert.objects.filter(meter=meter, alert_type="leak").exclude(status=Alert.Status.RESOLVED).exists():
            continue
        leaking = sorted(d for d in recent if night_min[d] > max(baseline * 2.5, baseline + 0.5))
        if not leaking:
            continue
        day = leaking[-1]
        flow = night_min[day]
        excess = (flow - baseline) * 24
        name = meter.building.name if meter.building else meter.name
        _raise(created, dedupe_key=f"leak:{meter.id}:{day}", building=meter.building, meter=meter,
               category=Alert.Category.WATER, alert_type="leak",
               severity=_severity(excess, (20, 50, 150)),
               title=f"{name}: possible water leak",
               message=(f"Minimum night-time flow (01:00-05:00) has been {flow:.2f} kL/h against a normal "
                        f"{baseline:.2f} kL/h on {len(leaking)} of the last {len(recent)} nights (since "
                        f"{leaking[0]:%d %b}). Continuous night flow usually means a leak, an overflowing tank "
                        f"or a running tap. Estimated loss {excess:.0f} kL/day."),
               excess_quantity=round(excess, 1), excess_unit="kL",
               estimated_cost=round(excess * settings.water_tariff), occurred_on=day)


def _stuck_and_suspect(created, now):
    since = now - timedelta(hours=RECENT_HOURS)
    for meter in Meter.objects.filter(is_active=True, last_reading_at__gte=since).select_related("building"):
        last = list(Reading.objects.filter(meter=meter).order_by("-timestamp").values_list("value", flat=True)[:6])
        if len(last) == 6 and last[0] > 0 and len(set(last)) == 1:
            _raise(created, dedupe_key=f"stuck:{meter.id}:{now.date()}", building=meter.building, meter=meter,
                   category=Alert.Category.DATA, alert_type="stuck", severity=Alert.Severity.MEDIUM,
                   title=f"{meter.name}: sensor appears stuck",
                   message=f"The last 6 readings were all exactly {last[0]} {meter.unit}. Check the meter "
                           "and its communication link; data from it is flagged until fixed.",
                   occurred_on=now.date())

    suspects = (Reading.objects.filter(quality=Reading.Quality.SUSPECT, timestamp__gte=since)
                .select_related("meter", "meter__building"))
    seen = set()
    for reading in suspects:
        day = timezone.localtime(reading.timestamp).date()
        if (reading.meter_id, day) in seen:
            continue
        seen.add((reading.meter_id, day))
        meter = reading.meter
        _raise(created, dedupe_key=f"suspect:{meter.id}:{day}", building=meter.building, meter=meter,
               category=Alert.Category.DATA, alert_type="impossible_value", severity=Alert.Severity.LOW,
               title=f"{meter.name}: impossible reading received",
               message=f"A reading of {reading.value} {meter.unit} is outside the physical range of this meter "
                       "and has been flagged (not deleted) for review.",
               occurred_on=day)


def _offline(created, now):
    stale = Meter.objects.filter(is_active=True).exclude(last_reading_at__gte=now - OFFLINE_AFTER)
    names = list(stale.values_list("name", flat=True))
    if names:
        listed = ", ".join(names[:8]) + (f" and {len(names) - 8} more" if len(names) > 8 else "")
        _raise(created, dedupe_key=f"offline:{now.date()}", category=Alert.Category.DATA, alert_type="offline",
               severity=Alert.Severity.HIGH if len(names) > 5 else Alert.Severity.MEDIUM,
               title=f"{len(names)} meter(s) not reporting",
               message=f"No data for more than 3 hours from: {listed}. Readings are buffered at the gateway; "
                       "check network connectivity and power to the devices.",
               occurred_on=now.date())


def _co2(created, now):
    rows = (EnvReading.objects.filter(timestamp__gte=now - timedelta(hours=24), co2_ppm__gt=CO2_LIMIT)
            .select_related("building").order_by("-co2_ppm"))
    seen = set()
    for row in rows:
        day = timezone.localtime(row.timestamp).date()
        if (row.building_id, day) in seen:
            continue
        seen.add((row.building_id, day))
        _raise(created, dedupe_key=f"co2:{row.building_id}:{day}", building=row.building,
               category=Alert.Category.ENVIRONMENT, alert_type="co2_high", severity=Alert.Severity.MEDIUM,
               title=f"{row.building.name}: poor ventilation (CO2 {row.co2_ppm:.0f} ppm)",
               message=f"Indoor CO2 reached {row.co2_ppm:.0f} ppm at {timezone.localtime(row.timestamp):%H:%M} "
                       f"with {row.occupancy} occupants. Increase fresh-air intake; above {CO2_LIMIT} ppm "
                       "concentration and comfort drop.",
               occurred_on=day)


def building_status():
    """Open alert counts per building for the operations console."""
    counts = defaultdict(int)
    for building_id in Alert.objects.exclude(status=Alert.Status.RESOLVED).values_list("building_id", flat=True):
        counts[building_id] += 1
    return {b.id: counts.get(b.id, 0) for b in Building.objects.all()}
