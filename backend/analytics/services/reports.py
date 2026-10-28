"""GHG Protocol inventory report (PDF via ReportLab) and CSV exports."""

import csv
import io
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from monitoring.models import Alert, Building, CampusSettings, Meter
from sustainability.models import EmissionFactor, FuelLog, WasteLog

from .carbon import CATEGORY_LABELS, FactorBook, emission_items, group
from .common import daily_totals, readings
from .insights import overview

GREEN = colors.HexColor("#1f7a4d")


def _table(rows, widths=None):
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f6f3")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d6cf")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def ghg_pdf(rng):
    settings = CampusSettings.load()
    data = overview(rng)
    items = emission_items(rng)
    buildings = {b.id: b.name for b in Building.objects.all()}
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontSize = 9
    body.leading = 12
    h1, h2 = styles["Title"], styles["Heading2"]
    h2.textColor = GREEN

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title="GHG Inventory Report", author=settings.name)
    end = rng.end - timedelta(days=1)
    story = [
        Paragraph("Greenhouse Gas Inventory Report", h1),
        Paragraph(f"<b>{settings.name}</b><br/>Reporting period: {rng.start:%d %b %Y} to {end:%d %b %Y} "
                  f"({data['range']['data_days']} days with data)<br/>Prepared {timezone.localtime():%d %b %Y %H:%M} "
                  "by the Smart Campus Sustainability and Carbon Footprint Monitoring System", body),
        Spacer(1, 8),
        Paragraph("1. Summary", h2),
    ]
    c = data["carbon"]
    story.append(_table([
        ["Indicator", "Value"],
        ["Total emissions (period)", f"{c['total_tco2e']:,.1f} tCO2e"],
        ["Annualised emissions", f"{c['annualised_tco2e']:,.0f} tCO2e / year"],
        ["Per student (annualised)", f"{c['per_student_t']:.3f} tCO2e"],
        ["Per square metre (annualised)", f"{c['per_m2_kg']:.1f} kgCO2e / m2"],
        ["Scope 2 - location based", f"{c['scope2_t']:,.1f} tCO2e"],
        ["Scope 2 - market based", f"{c['scope2_market_t']:,.1f} tCO2e"],
        ["Renewable share of electricity", f"{data['energy']['renewable_share_pct']}%"],
        ["Energy Performance Index", f"{data['energy']['eui_kwh_m2_yr']} kWh/m2/year"],
        ["Water use", f"{data['water']['litres_per_person_day']} L / person / day"],
        ["Waste diversion rate", f"{data['waste']['diversion_rate_pct']}%"],
        ["Tree sequestration (reported separately)", f"{c['sequestration_t_per_year']} tCO2 / year"],
    ], [95 * mm, 75 * mm]))

    story += [Spacer(1, 6), Paragraph("2. Emissions by scope and source", h2)]
    rows = [["Scope", "Source", "Activity data", "tCO2e", "Share"]]
    total = sum(i.kg for i in items) or 1
    by_key = defaultdict(lambda: [0.0, 0.0, ""])
    for i in items:
        entry = by_key[(i.scope, i.category)]
        entry[0] += i.quantity
        entry[1] += i.kg
        entry[2] = i.unit
    for (scope, cat), (qty, kg, unit) in sorted(by_key.items(), key=lambda x: (x[0][0], -x[1][1])):
        rows.append([f"Scope {scope}", CATEGORY_LABELS.get(cat, cat), f"{qty:,.0f} {unit}", f"{kg / 1000:,.2f}",
                     f"{kg / total * 100:.1f}%"])
    rows.append(["", "Total", "", f"{total / 1000:,.2f}", "100%"])
    story.append(_table(rows, [20 * mm, 55 * mm, 40 * mm, 30 * mm, 25 * mm]))

    story += [Spacer(1, 6), Paragraph("3. Emissions by building (Scope 2 electricity, water and logged sources)", h2)]
    by_b = group([i for i in items if i.building_id], lambda i: i.building_id)
    rows = [["Building", "tCO2e"]] + [[buildings.get(k, "-"), f"{v / 1000:,.2f}"]
                                      for k, v in sorted(by_b.items(), key=lambda x: -x[1])]
    story.append(_table(rows, [120 * mm, 50 * mm]))

    story += [Spacer(1, 6), Paragraph("4. Monthly trend", h2)]
    rows = [["Month", "Scope 1", "Scope 2", "Scope 3", "Total"]]
    for m in data["monthly"]:
        rows.append([m["month"], f"{m['scope1']:,.1f}", f"{m['scope2']:,.1f}", f"{m['scope3']:,.1f}",
                     f"{m['scope1'] + m['scope2'] + m['scope3']:,.1f}"])
    story.append(_table(rows, [34 * mm] * 5))

    if data["target"]:
        t = data["target"]
        story += [Spacer(1, 6), Paragraph("5. Progress against target", h2), Paragraph(
            f"{t['name']}: reduce from {t['baseline_tco2e']:,.0f} tCO2e ({t['baseline_year']}) by "
            f"{t['reduction_pct_required']}% to {t['target_tco2e']:,.0f} tCO2e by {t['target_year']}. Current "
            f"annualised emissions represent a {t['reduction_achieved_pct']}% change against baseline "
            f"({t['progress_pct']}% of the way to target).", body)]

    story += [Spacer(1, 6), Paragraph("6. Methodology and emission factors", h2), Paragraph(
        "Prepared following the GHG Protocol Corporate Accounting and Reporting Standard (operational control). "
        "Emissions = activity data x emission factor, applied per day using the factor version valid on that "
        "day. Scope 3 commuting is estimated from anonymous surveys scaled to the campus population. "
        f"Organisational boundary: {settings.boundary_notes} Factors are indicative defaults and must be checked "
        "against the latest official publications (e.g. CEA CO2 Baseline Database) before external disclosure.",
        body), Spacer(1, 4)]
    book = FactorBook()
    used = sorted({i.activity for i in items})
    rows = [["Activity", "Scope", "Factor", "Version", "Source"]]
    for activity in used:
        f = book.get(activity, end)
        if f:
            rows.append([f.get_activity_display(), str(f.scope), f"{f.value:g} kg/{f.activity_unit}", f"v{f.version}",
                         Paragraph(f.source, body)])
    story.append(_table(rows, [45 * mm, 13 * mm, 32 * mm, 15 * mm, 65 * mm]))

    doc.build(story)
    return buf.getvalue()


def _write(rows, header):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def export_csv(dataset, rng):
    buildings = {b.id: b.name for b in Building.objects.all()}
    if dataset == "emissions":
        rows = [[i.day, f"Scope {i.scope}", CATEGORY_LABELS.get(i.category, i.category), i.activity,
                 buildings.get(i.building_id, "Campus"), round(i.quantity, 3), i.unit, round(i.kg, 3)]
                for i in sorted(emission_items(rng), key=lambda i: (i.day, i.scope))]
        return _write(rows, ["date", "scope", "category", "activity", "building", "quantity", "unit", "kgCO2e"])
    if dataset in ("electricity", "solar", "water"):
        kind = {"electricity": Meter.Kind.ELECTRICITY, "solar": Meter.Kind.SOLAR, "water": Meter.Kind.WATER}[dataset]
        unit = "kL" if dataset == "water" else "kWh"
        rows = [[row["day"], buildings.get(row["meter__building_id"], "-"), round(row["total"], 3), unit]
                for row in daily_totals(readings(kind, rng), "meter__building_id")]
        return _write(rows, ["date", "building", "total", "unit"])
    if dataset == "waste":
        rows = [[w.date, buildings.get(w.building_id, "Campus"), w.get_category_display(), w.get_disposal_display(),
                 w.weight_kg] for w in WasteLog.objects.filter(date__gte=rng.start, date__lt=rng.end)]
        return _write(rows, ["date", "building", "category", "disposal", "weight_kg"])
    if dataset == "fuel":
        rows = [[f.date, f.get_category_display(), f.get_activity_display(), f.quantity, f.asset, f.distance_km or ""]
                for f in FuelLog.objects.filter(date__gte=rng.start, date__lt=rng.end)]
        return _write(rows, ["date", "category", "fuel", "quantity", "asset", "distance_km"])
    if dataset == "alerts":
        rows = [[a.occurred_on, a.get_category_display(), a.alert_type, a.severity, a.status, a.title,
                 a.excess_quantity, a.excess_unit, a.estimated_cost]
                for a in Alert.objects.filter(occurred_on__gte=rng.start, occurred_on__lt=rng.end)]
        return _write(rows, ["date", "category", "type", "severity", "status", "title", "excess", "unit", "cost_inr"])
    if dataset == "factors":
        rows = [[f.get_activity_display(), f.scope, f.value, f.activity_unit, f.valid_from, f.version, f.source]
                for f in EmissionFactor.objects.all()]
        return _write(rows, ["activity", "scope", "kgCO2e_per_unit", "unit", "valid_from", "version", "source"])
    return None


CSV_DATASETS = ["emissions", "electricity", "solar", "water", "waste", "fuel", "alerts", "factors"]
