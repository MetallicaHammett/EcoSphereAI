"""
Electricity demand forecast.

A transparent multiple linear regression fitted with NumPy least squares:
    kWh/day ~ trend + day-of-week + holiday + mean outdoor temperature
Simple enough to explain in a viva, and accurate for campus loads which are driven
mostly by the academic calendar and cooling demand.
"""

from datetime import timedelta

import numpy as np
from django.db.models import Avg
from django.db.models.functions import TruncDate
from django.utils import timezone

from monitoring.models import CampusSettings, Meter, WeatherReading

from .carbon import FactorBook
from .common import daily_totals, day_start, non_working_days, readings

HISTORY_DAYS = 120
MIN_POINTS = 21


def _features(day, index, n, off_days, temp):
    dow = [1.0 if day.weekday() == k else 0.0 for k in range(6)]  # Sunday is the reference level
    return [1.0, index / n, *dow, 1.0 if day in off_days and day.weekday() < 5 else 0.0, temp - 28.0]


def forecast(days_ahead=30, building_id=None):
    today = timezone.localdate()
    start = today - timedelta(days=HISTORY_DAYS)
    history = {row["day"]: row["total"] for row in daily_totals(
        readings(Meter.Kind.ELECTRICITY, start=day_start(start), end=day_start(today), building_id=building_id))}
    temps = {row["day"]: row["t"] for row in WeatherReading.objects
             .filter(timestamp__gte=day_start(start), timestamp__lt=day_start(today))
             .annotate(day=TruncDate("timestamp")).values("day").annotate(t=Avg("temperature"))}

    # Ignore a trailing partial day and days with obviously missing data.
    days = sorted(d for d, v in history.items() if v > 0)
    if days:
        typical = float(np.median([history[d] for d in days]))
        days = [d for d in days if history[d] > 0.2 * typical]
    if len(days) < MIN_POINTS:
        return {"error": f"At least {MIN_POINTS} days of electricity data are needed; found {len(days)}."}

    horizon_end = today + timedelta(days=days_ahead)
    off_days = non_working_days(start, horizon_end + timedelta(days=1))
    recent_temps = [temps[d] for d in days[-14:] if d in temps]
    future_temp = float(np.mean(recent_temps)) if recent_temps else 28.0
    n = (horizon_end - start).days

    X = np.array([_features(d, (d - start).days, n, off_days, temps.get(d, future_temp)) for d in days])
    y = np.array([history[d] for d in days])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    fitted = X @ beta
    residuals = y - fitted
    sigma = float(np.std(residuals, ddof=min(len(beta), len(y) - 1)))
    mape = float(np.mean(np.abs(residuals) / y) * 100)
    r2 = float(1 - np.sum(residuals ** 2) / np.sum((y - y.mean()) ** 2)) if len(y) > 1 else 0.0

    book = FactorBook()
    tariff = CampusSettings.load().electricity_tariff
    future = []
    for i in range(days_ahead):
        d = today + timedelta(days=i)
        value = max(float(np.dot(_features(d, (d - start).days, n, off_days, future_temp), beta)), 0.0)
        future.append({
            "date": d.isoformat(),
            "forecast": round(value, 1),
            "lower": round(max(value - 1.96 * sigma, 0.0), 1),
            "upper": round(value + 1.96 * sigma, 1),
            "non_working": d in off_days,
        })
    total = sum(f["forecast"] for f in future)
    factor = book.value("electricity_grid")
    return {
        "history": [{"date": d.isoformat(), "actual": round(history[d], 1), "fitted": round(float(f), 1),
                     "non_working": d in off_days} for d, f in list(zip(days, fitted))[-60:]],
        "forecast": future,
        "model": {
            "method": "Multiple linear regression (trend, weekday, holiday, temperature) - NumPy least squares",
            "training_days": len(days),
            "mape_pct": round(mape, 2),
            "r2": round(r2, 3),
            "assumed_temperature_c": round(future_temp, 1),
            "temperature_sensitivity_kwh_per_c": round(float(beta[-1]), 1),
        },
        "totals": {
            "kwh": round(total, 0),
            "tco2e": round(total * factor / 1000, 2),
            "cost": round(total * tariff, 0),
            "peak_day": max(future, key=lambda f: f["forecast"])["date"] if future else None,
        },
    }
