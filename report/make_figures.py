"""Generates the report's charts from the running system's own data (run from the backend folder)."""

import os
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from statistics import median

sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from django.utils import timezone  # noqa: E402

from analytics.services import forecast, insights, scenarios  # noqa: E402
from analytics.services.common import DateRange, hourly_by_meter, non_working_days, parse_range  # noqa: E402
from monitoring.models import Building, Meter  # noqa: E402

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)
GREEN, BLUE, ORANGE, PURPLE, GOLD, TEAL, GREY = "#1f7a4d", "#3b82c4", "#e07a3f", "#8b6cc1", "#f2b33d", "#2a9bb5", "#9aa9a1"
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.3,
                     "figure.dpi": 200, "savefig.bbox": "tight"})


def save(name):
    plt.savefig(OUT / f"{name}.png")
    plt.close()
    print("saved", name)


today = timezone.localdate()

# 1. Monthly emissions by scope
ov = insights.overview(parse_range({"days": 120}))
months = [m["month"] for m in ov["monthly"]]
s1 = [m["scope1"] for m in ov["monthly"]]
s2 = [m["scope2"] for m in ov["monthly"]]
s3 = [m["scope3"] for m in ov["monthly"]]
fig, ax = plt.subplots(figsize=(7, 3.2))
ax.bar(months, s1, color=ORANGE, label="Scope 1")
ax.bar(months, s2, bottom=s1, color=BLUE, label="Scope 2")
ax.bar(months, s3, bottom=[a + b for a, b in zip(s1, s2)], color=PURPLE, label="Scope 3")
ax.set_ylabel("tCO$_2$e")
ax.legend(frameon=False, ncol=3)
ax.set_title("Monthly emissions by scope (first and last months are partial)")
save("fig_scope_monthly")

# 2. Emissions by source (30 days)
ov30 = insights.overview(parse_range({"days": 30}))
cats = ov30["by_category"][::-1]
fig, ax = plt.subplots(figsize=(7, 3))
ax.barh([c["category"] for c in cats], [c["tco2e"] for c in cats], color=GREEN)
for i, c in enumerate(cats):
    ax.text(c["tco2e"], i, f" {c['tco2e']:.1f}", va="center", fontsize=9)
ax.set_xlabel("tCO$_2$e in the last 30 days")
ax.set_title("Emissions by source")
save("fig_sources")

# 3. Average working-day load profile by building type
start = timezone.now() - timedelta(days=28)
meters = list(Meter.objects.filter(kind__in=["electricity", "solar"]).select_related("building"))
series = hourly_by_meter([m.id for m in meters], start, timezone.now())
off = non_working_days(today - timedelta(days=29), today + timedelta(days=1))
profile = defaultdict(lambda: defaultdict(list))
for m in meters:
    totals = defaultdict(float)
    for ts, v in series[m.id].items():
        totals[ts] += v
    for ts, v in totals.items():
        if ts.date() not in off:
            profile[m.building.type][ts.hour].append(v / m.building.area_m2 * 1000)
fig, ax = plt.subplots(figsize=(7, 3.2))
for btype, color in (("academic", BLUE), ("lab", PURPLE), ("hostel", ORANGE), ("library", TEAL), ("canteen", GOLD)):
    hours = sorted(profile[btype])
    days_total = defaultdict(float)
    ax.plot(hours, [sum(profile[btype][h]) / len(profile[btype][h]) for h in hours], label=btype.title(), color=color, lw=2)
ax.set_xlabel("Hour of day")
ax.set_ylabel("W per m$^2$ (load incl. solar)")
ax.set_xticks(range(0, 24, 3))
ax.legend(frameon=False, ncol=5, fontsize=8)
ax.set_title("Average working-day load profile by building type (last 4 weeks)")
save("fig_load_profile")

# 4. Grid vs solar, Academic Block A, last 7 days
aca = Building.objects.get(code="ACA")
em, sm = Meter.objects.get(serial="EM-ACA"), Meter.objects.get(serial="SM-ACA")
s7 = timezone.now() - timedelta(days=7)
ser = hourly_by_meter([em.id, sm.id], s7, timezone.now())
ts = sorted(t for t in ser[em.id] if t < timezone.localtime().replace(minute=0, second=0, microsecond=0))
fig, ax = plt.subplots(figsize=(7, 2.8))
ax.stackplot(ts, [ser[em.id][t] for t in ts], [ser[sm.id].get(t, 0) for t in ts], colors=[BLUE, GOLD],
             labels=["Grid draw", "Rooftop solar"], alpha=0.8)
ax.set_ylabel("kWh per hour")
ax.legend(frameon=False, loc="upper left")
ax.set_title(f"{aca.name}: grid and solar, last 7 days")
fig.autofmt_xdate()
save("fig_grid_solar")

# 5. Anomaly: Academic Block B night load vs learnt profile
acb = Meter.objects.get(serial="EM-ACB")
base_start = timezone.now() - timedelta(days=32)
ser = hourly_by_meter([acb.id], base_start, timezone.now())[acb.id]
recent_cut = timezone.localtime() - timedelta(hours=50)
offd = non_working_days((timezone.now() - timedelta(days=33)).date(), today + timedelta(days=1))
buckets = defaultdict(list)
for t, v in ser.items():
    if t < recent_cut:
        buckets[(t.date() in offd, t.hour)].append(v)
hour_now = timezone.localtime().replace(minute=0, second=0, microsecond=0)
last = sorted(t for t in ser if timezone.localtime() - timedelta(days=4) <= t < hour_now)
expected = [median(buckets[(t.date() in offd, t.hour)]) for t in last]
fig, ax = plt.subplots(figsize=(7, 2.8))
ax.plot(last, [ser[t] for t in last], color=BLUE, lw=2, label="Measured")
ax.plot(last, expected, color=GREY, ls="--", label="Learnt normal profile (median)")
flag = [t for t, e in zip(last, expected) if ser[t] - e > max(0.2 * e, 25)]
ax.scatter(flag, [ser[t] for t in flag], color=ORANGE, zorder=3, s=14, label="Flagged hours")
ax.set_ylabel("kWh per hour")
ax.legend(frameon=False, fontsize=8)
ax.set_title("Academic Block B: air-conditioning left on overnight detected")
fig.autofmt_xdate()
save("fig_anomaly")

# 6. Leak: Boys Hostel 1 minimum night flow
wm = Meter.objects.get(serial="WM-BH1")
ser = hourly_by_meter([wm.id], timezone.now() - timedelta(days=30), timezone.now())[wm.id]
nights = defaultdict(list)
for t, v in ser.items():
    if 1 <= t.hour <= 4:
        nights[t.date()].append(v)
days = sorted(d for d in nights if len(nights[d]) >= 3)
mins = [min(nights[d]) for d in days]
base = median(mins[:-4])
fig, ax = plt.subplots(figsize=(7, 2.6))
ax.bar(days, mins, color=[ORANGE if m > max(base * 2.5, base + 0.5) else TEAL for m in mins])
ax.axhline(max(base * 2.5, base + 0.5), color="black", ls="--", lw=1, label="Leak threshold")
ax.set_ylabel("kL per hour")
ax.legend(frameon=False)
ax.set_title("Boys Hostel 1: minimum flow between 01:00 and 05:00 each night")
fig.autofmt_xdate()
save("fig_leak")

# 7. Forecast
fc = forecast.forecast(30)
fig, ax = plt.subplots(figsize=(7, 3))
hd = [h["date"] for h in fc["history"]]
ax.plot(hd, [h["actual"] / 1000 for h in fc["history"]], color=BLUE, label="Actual")
ax.plot(hd, [h["fitted"] / 1000 for h in fc["history"]], color=GREY, ls="--", label="Model fit")
fd = [f["date"] for f in fc["forecast"]]
ax.plot(fd, [f["forecast"] / 1000 for f in fc["forecast"]], color=GREEN, lw=2, label="Forecast")
ax.fill_between(fd, [f["lower"] / 1000 for f in fc["forecast"]], [f["upper"] / 1000 for f in fc["forecast"]],
                color=GREEN, alpha=0.15, label="95% interval")
ax.set_xticks([d for i, d in enumerate(hd + fd) if i % 10 == 0])
ax.set_ylabel("MWh per day")
ax.legend(frameon=False, ncol=4, fontsize=8)
ax.set_title(f"Daily grid electricity forecast (MAPE {fc['model']['mape_pct']}%, R$^2$ {fc['model']['r2']})")
fig.autofmt_xdate()
save("fig_forecast")

# 8. Benchmark
bm = insights.benchmark(parse_range({"days": 30}))["buildings"][::-1]
fig, ax = plt.subplots(figsize=(7, 3))
colors = [GREEN if b["stars"] >= 4 else GOLD if b["stars"] == 3 else ORANGE for b in bm]
ax.barh([b["building"] for b in bm], [b["eui_kwh_m2_yr"] for b in bm], color=colors)
ax.set_xlabel("Energy Performance Index (kWh/m$^2$/year)")
ax.set_title("Building benchmarking (lower is better)")
save("fig_benchmark")

# 9. Waste diversion trend + commute mode share
ws = insights.waste(parse_range({"days": 119}))
tr = insights.transport(parse_range({"days": 30}))
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.9))
weeks = ws["weekly"][1:-1]
from sustainability.models import WasteLog  # noqa: E402
rates = []
for w in weeks:
    from datetime import date as _d
    ws_start = _d.fromisoformat(w["week"])
    logs = WasteLog.objects.filter(date__gte=ws_start, date__lt=ws_start + timedelta(days=7))
    tot = sum(l.weight_kg for l in logs)
    div = sum(l.weight_kg for l in logs if l.disposal in WasteLog.DIVERTED)
    rates.append(div / tot * 100 if tot else 0)
a1.plot(range(1, len(rates) + 1), rates, color=GREEN, marker="o", ms=3)
a1.set_xlabel("Week")
a1.set_ylabel("Diversion rate (%)")
a1.set_title("Waste diversion trend")
modes = sorted(tr["modes"], key=lambda m: m["share_pct"])
a2.barh([m["label"] for m in modes], [m["share_pct"] for m in modes],
        color=[GREEN if m["sustainable"] else ORANGE for m in modes])
a2.set_xlabel("% of respondents")
a2.set_title("Commute mode share")
a2.tick_params(axis="y", labelsize=8)
plt.tight_layout()
save("fig_waste_commute")

# 10. Scenario
sc = scenarios.run({"led_coverage_pct": 50, "solar_kwp": 250, "setpoint_increase_c": 1, "smart_controls_pct": 30,
                    "electric_buses": 2})
fig, ax = plt.subplots(figsize=(7, 2.8))
ms = sc["measures"]
ax.bar([m["name"].replace(" ", "\n", 2) for m in ms], [m["tco2e_saved"] for m in ms],
       color=[GREEN if m["tco2e_saved"] >= 0 else ORANGE for m in ms])
ax.axhline(0, color="black", lw=0.6)
ax.set_ylabel("tCO$_2$e avoided per year")
ax.tick_params(axis="x", labelsize=8)
ax.set_title("Scenario model: impact of individual measures")
save("fig_scenario")

import json  # noqa: E402

(OUT / "numbers.json").write_text(json.dumps({
    "overview30": {k: ov30[k] for k in ("carbon", "energy", "water", "waste", "transport", "target")},
    "forecast": fc["model"] | fc["totals"],
    "scenario": sc["totals"] | {"measures": [(m["name"], m["tco2e_saved"], m["annual_saving_inr"], m["capex_inr"], m["payback_years"]) for m in ms]},
    "benchmark": [(b["building"], b["eui_kwh_m2_yr"], b["stars"]) for b in bm[::-1]],
    "transport": tr["totals"], "waste": ws["totals"],
}, default=str, indent=1))
