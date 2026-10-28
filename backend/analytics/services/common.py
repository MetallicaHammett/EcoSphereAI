"""Date-range parsing and time-series helpers shared by the analytics services."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from django.utils.dateparse import parse_date

from monitoring.models import CalendarDay, Reading

MAX_RANGE_DAYS = 800


class RangeError(ValueError):
    pass


@dataclass(frozen=True)
class DateRange:
    start: date  # inclusive
    end: date  # exclusive

    @property
    def start_dt(self):
        return day_start(self.start)

    @property
    def end_dt(self):
        return day_start(self.end)

    @property
    def days(self):
        return (self.end - self.start).days

    def dates(self):
        return [self.start + timedelta(days=i) for i in range(self.days)]


def day_start(d):
    return timezone.make_aware(datetime.combine(d, time.min))


def parse_range(params, default_days=30):
    """Accepts ``?days=N``, ``?period=ytd`` or ``?start=YYYY-MM-DD&end=YYYY-MM-DD`` (end inclusive)."""
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    if params.get("start") or params.get("end"):
        start = parse_date(params.get("start") or "")
        end = parse_date(params.get("end") or "")
        if not start or not end:
            raise RangeError("start and end must both be dates in YYYY-MM-DD format.")
        if end < start:
            raise RangeError("end must not be before start.")
        rng = DateRange(start, end + timedelta(days=1))
    elif params.get("period") == "ytd":
        rng = DateRange(date(today.year, 1, 1), tomorrow)
    else:
        try:
            days = int(params.get("days", default_days))
        except (TypeError, ValueError):
            raise RangeError("days must be a whole number.")
        if days < 1:
            raise RangeError("days must be at least 1.")
        rng = DateRange(tomorrow - timedelta(days=days), tomorrow)
    if rng.days > MAX_RANGE_DAYS:
        raise RangeError(f"Range is limited to {MAX_RANGE_DAYS} days.")
    return rng


def readings(kind=None, rng=None, start=None, end=None, building_id=None, meter_ids=None):
    """Valid readings only: suspect values are kept for review but never counted."""
    qs = Reading.objects.exclude(quality=Reading.Quality.SUSPECT)
    if kind:
        qs = qs.filter(meter__kind=kind) if isinstance(kind, str) else qs.filter(meter__kind__in=kind)
    if rng is not None:
        start, end = rng.start_dt, rng.end_dt
    if start is not None:
        qs = qs.filter(timestamp__gte=start)
    if end is not None:
        qs = qs.filter(timestamp__lt=end)
    if building_id:
        qs = qs.filter(meter__building_id=building_id)
    if meter_ids is not None:
        qs = qs.filter(meter_id__in=meter_ids)
    return qs


def daily_totals(qs, *group):
    """Sum of readings per local day, optionally split by extra fields."""
    return qs.annotate(day=TruncDate("timestamp")).values("day", *group).annotate(total=Sum("value")).order_by("day")


def hourly_totals(qs, *group):
    return qs.annotate(hour=TruncHour("timestamp")).values("hour", *group).annotate(total=Sum("value")).order_by("hour")


def hourly_by_meter(meter_ids, start, end):
    """{meter_id: {local hour datetime: kWh or kL}} for complete-hour analysis."""
    result = defaultdict(dict)
    for row in hourly_totals(readings(start=start, end=end, meter_ids=meter_ids), "meter_id"):
        result[row["meter_id"]][timezone.localtime(row["hour"])] = row["total"]
    return result


def data_days(qs):
    """How many distinct days actually have data, so partial periods are annualised honestly."""
    return qs.annotate(day=TruncDate("timestamp")).values("day").annotate(n=Count("id")).count()


def non_working_days(start, end):
    """Weekends plus calendar holidays/vacations between two dates."""
    special = set(CalendarDay.objects.filter(date__gte=start, date__lt=end)
                  .exclude(kind=CalendarDay.Kind.EXAM).values_list("date", flat=True))
    days = set()
    d = start
    while d < end:
        if d.weekday() >= 5 or d in special:
            days.add(d)
        d += timedelta(days=1)
    return days


def safe_div(a, b):
    return a / b if b else 0.0


def r(value, digits=2):
    return round(float(value or 0), digits)
