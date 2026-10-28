"""
Builds the project report PDF.

The original cover page and bonafide certificate are copied unchanged from the PDF the team
supplied; everything after them is generated here with ReportLab.

    python report/build_report.py "<path to original pdf>"
"""

import json
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable, Frame, Image, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Preformatted, Spacer, Table, TableStyle)

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
N = json.loads((FIG / "numbers.json").read_text())
TITLE = "Smart Campus Sustainability and Carbon Footprint Monitoring System"

FONTS = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Times", FONTS / "times.ttf"))
pdfmetrics.registerFont(TTFont("Times-B", FONTS / "timesbd.ttf"))
pdfmetrics.registerFont(TTFont("Times-I", FONTS / "timesi.ttf"))
pdfmetrics.registerFont(TTFont("Times-BI", FONTS / "timesbi.ttf"))
pdfmetrics.registerFont(TTFont("Cour", FONTS / "cour.ttf"))
pdfmetrics.registerFont(TTFont("Arial", FONTS / "arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-B", FONTS / "arialbd.ttf"))
pdfmetrics.registerFontFamily("Times", normal="Times", bold="Times-B", italic="Times-I", boldItalic="Times-BI")

GREEN = colors.HexColor("#1f5e3d")
LIGHT = colors.HexColor("#eef4f0")
GRID = colors.HexColor("#9fb5a8")

# ------------------------------------------------------------------ styles
body = ParagraphStyle("body", fontName="Times", fontSize=11, leading=14.6, alignment=TA_JUSTIFY, spaceAfter=5)
bullet = ParagraphStyle("bullet", parent=body, leftIndent=18, bulletIndent=6, spaceAfter=2)
h_chapter_no = ParagraphStyle("chno", fontName="Times-B", fontSize=13, alignment=TA_CENTER, spaceAfter=4,
                              textColor=GREEN)
h_chapter = ParagraphStyle("ch", fontName="Times-B", fontSize=15, alignment=TA_CENTER, spaceAfter=8, leading=18)
h1 = ParagraphStyle("h1", fontName="Times-B", fontSize=12.5, spaceBefore=7, spaceAfter=4, leading=15)
h2 = ParagraphStyle("h2", fontName="Times-BI", fontSize=12, spaceBefore=6, spaceAfter=4, leading=15)
caption = ParagraphStyle("cap", fontName="Times-I", fontSize=10, alignment=TA_CENTER, spaceBefore=2, spaceAfter=7)
cell = ParagraphStyle("cell", fontName="Times", fontSize=10.5, leading=13, alignment=TA_LEFT)
cell_b = ParagraphStyle("cellb", parent=cell, fontName="Times-B", textColor=colors.white)
eq = ParagraphStyle("eq", fontName="Times-I", fontSize=12, alignment=TA_CENTER, spaceBefore=4, spaceAfter=8, leading=18)
code = ParagraphStyle("code", fontName="Cour", fontSize=8.6, leading=10.8, backColor=colors.HexColor("#f4f6f5"),
                      borderColor=colors.HexColor("#d5dfd9"), borderWidth=0.5, borderPadding=6, leftIndent=6,
                      rightIndent=6, spaceBefore=4, spaceAfter=10)
front_title = ParagraphStyle("ft", fontName="Times-B", fontSize=15, alignment=TA_CENTER, spaceAfter=12)

figures, tables = [], []


def P(text, style=body):
    return Paragraph(text, style)


def bullets(items, style=bullet):
    return [Paragraph(i, style, bulletText="\u2022") for i in items]


def numbered(items):
    return [Paragraph(i, bullet, bulletText=f"{n}.") for n, i in enumerate(items, 1)]


class Anchor(Flowable):
    """Zero-size marker; its draw() records page numbers for the TOC."""

    def __init__(self, kind, text, level=0):
        super().__init__()
        self.kind, self.text, self.level = kind, text, level

    def wrap(self, *a):
        return 0, 0

    def draw(self):
        doc = self.canv._doctemplate
        if self.kind == "arabic":
            doc.arabic_start = doc.page
        else:
            TOC_ENTRIES.append((self.level, self.text, doc.label(doc.page)))
            self.canv.bookmarkPage(f"k{id(self)}")
            self.canv.addOutlineEntry(self.text, f"k{id(self)}", level=self.level)


TOC_ENTRIES = []
chapter_no = [0]
section_no = [0]


def chapter(title):
    chapter_no[0] += 1
    section_no[0] = 0
    return [CondPageBreak(8 * cm), Spacer(1, 8), Anchor("toc", f"{chapter_no[0]}.  {title.upper()}", 0),
            P(f"CHAPTER {chapter_no[0]}", h_chapter_no), P(title.upper(), h_chapter)]


def unnumbered(title, need=8 * cm):
    return [CondPageBreak(need), Spacer(1, 10), Anchor("toc", title.upper(), 0), P(title.upper(), h_chapter)]


def section(title):
    section_no[0] += 1
    label = f"{chapter_no[0]}.{section_no[0]}  {title}"
    return [CondPageBreak(3 * cm), Anchor("toc", label, 1), P(label, h1)]


def sub(title):
    return P(title, h2)


PAGES = {}  # caption label -> printed page number, recorded while drawing


class PageMark(Flowable):
    def __init__(self, label):
        super().__init__()
        self.label = label

    def wrap(self, *a):
        return 0, 0

    def draw(self):
        doc = self.canv._doctemplate
        PAGES[self.label] = doc.label(doc.page)


def _label(kind, store):
    """Numbers figures and tables within each chapter, e.g. 'Figure 7.3'."""
    n = sum(1 for lab, _ in store if lab.startswith(f"{kind} {chapter_no[0]}.")) + 1
    return f"{kind} {chapter_no[0]}.{n}"


def figure(path, cap, width=11.5 * cm):
    label = _label("Figure", figures)
    figures.append((label, cap))
    img = ImageReader(str(path))
    w, h = img.getSize()
    height = width * h / w
    if height > 11.5 * cm:
        width, height = width * 11.5 * cm / height, 11.5 * cm
    return KeepTogether([Spacer(1, 4), PageMark(label), Image(str(path), width=width, height=height),
                         P(f"{label}: {cap}", caption)])


def drawing_figure(drawing, cap):
    label = _label("Figure", figures)
    figures.append((label, cap))
    return KeepTogether([Spacer(1, 4), PageMark(label), drawing, P(f"{label}: {cap}", caption)])


def table(rows, widths, cap, header=True, font=10.5):
    label = _label("Table", tables)
    tables.append((label, cap))
    style = ParagraphStyle("c", parent=cell, fontSize=font, leading=font + 2.5)
    head = ParagraphStyle("h", parent=cell_b, fontSize=font, leading=font + 2.5)
    data = [[Paragraph(str(c), head if (header and r == 0) else style) for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    cmds = [("GRID", (0, 0), (-1, -1), 0.5, GRID), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
            ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, LIGHT])]
    if header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), GREEN))
    t.setStyle(TableStyle(cmds))
    head_items = [PageMark(label), P(f"{label}: {cap}", ParagraphStyle("tc", parent=caption, spaceBefore=6,
                                                                       spaceAfter=4))]
    if len(rows) > 12:  # long tables may continue on the next page (header row repeats)
        return [CondPageBreak(3 * cm), *head_items, t, Spacer(1, 10)]
    return [KeepTogether([*head_items, t, Spacer(1, 10)])]


# ------------------------------------------------------------------ diagrams

def box(d, x, y, w, h, text, fill="#ffffff", stroke="#1f5e3d", size=8.5, bold=False, color="#15241c"):
    d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=colors.HexColor(fill), strokeColor=colors.HexColor(stroke),
               strokeWidth=0.9))
    lines = text.split("\n")
    total = len(lines) * (size + 2)
    for i, line in enumerate(lines):
        d.add(String(x + w / 2, y + h / 2 + total / 2 - (i + 1) * (size + 2) + 2.5, line, fontName="Arial-B" if bold
                     else "Arial", fontSize=size, fillColor=colors.HexColor(color), textAnchor="middle"))


def arrow(d, x1, y1, x2, y2, color="#1f5e3d"):
    d.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor(color), strokeWidth=1.1))
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    s = 5
    d.add(Polygon([x2, y2, x2 - s * math.cos(a - 0.4), y2 - s * math.sin(a - 0.4), x2 - s * math.cos(a + 0.4),
                   y2 - s * math.sin(a + 0.4)], fillColor=colors.HexColor(color), strokeColor=None))


def architecture_diagram():
    w, h = 450, 330
    d = Drawing(w, h)
    layers = [
        ("Application layer", "#e3efe8", ["Management\ndashboard", "Operations\nconsole", "Community\nportal",
                                          "Reports &\nexports", "Admin &\nsettings"]),
        ("Analytics & intelligence", "#e6eef8", ["Carbon engine\n(Scope 1/2/3)", "Anomaly\ndetection", "Demand\nforecast",
                                                 "Benchmarking", "Scenario\nmodelling"]),
        ("Data platform", "#f3ecf8", ["Validation &\nquality flags", "Time-series\nreadings", "Metadata &\nfactors",
                                      "Aggregation\n(hour/day/month)", "REST API\n(JWT, RBAC)"]),
        ("Connectivity", "#fbf1e6", ["Edge gateway\n(buffering)", "HTTP ingest\n+ device key", "MQTT / LoRaWAN\n(adapter)",
                                     "Wi-Fi / 4G", "Modbus\nRS-485"]),
        ("Sensing", "#fdf6df", ["Smart energy\nmeters", "Water flow &\nlevel", "Indoor CO2,\ntemp, occupancy",
                                "Solar &\nweather", "Waste scales,\nfleet logs"]),
    ]
    lh, gap = 54, 10
    for i, (name, fill, chips) in enumerate(layers):
        y = h - (i + 1) * (lh + gap) + gap
        d.add(Rect(0, y, w, lh, rx=6, ry=6, fillColor=colors.HexColor(fill), strokeColor=GRID, strokeWidth=0.7))
        d.add(String(8, y + lh - 13, name, fontName="Arial-B", fontSize=8.5, fillColor=GREEN))
        cw = (w - 20 - 4 * 6) / 5
        for j, chip in enumerate(chips):
            box(d, 10 + j * (cw + 6), y + 5, cw, lh - 22, chip, size=7.2)
        if i < len(layers) - 1:
            arrow(d, w - 14, y - gap + 1, w - 14, y - 1)
    return d


def dataflow_diagram():
    w, h = 450, 200
    d = Drawing(w, h)
    top = [("Meters /\nESP32 nodes", "#fdf6df"), ("Edge gateway\n(buffer + key)", "#fbf1e6"),
           ("POST /api/ingest/\nvalidate & flag", "#f3ecf8"), ("SQLite store\n(readings)", "#f3ecf8")]
    bw, bh, y1 = 92, 46, 140
    for i, (t, f) in enumerate(top):
        x = i * (bw + 27)
        box(d, x, y1, bw, bh, t, fill=f, size=8)
        if i:
            arrow(d, x - 27, y1 + bh / 2, x - 1, y1 + bh / 2)
    bottom = [("React dashboards\n(role based)", "#e3efe8"), ("REST API\n(JWT)", "#f3ecf8"),
              ("Analytics services\ncarbon / anomaly /\nforecast / scenarios", "#e6eef8")]
    y2 = 40
    xs = [0, 165, 330]
    for (t, f), x in zip(bottom, xs):
        box(d, x, y2, 120 if x != 165 else 92, 52, t, fill=f, size=8)
    arrow(d, 3 * (bw + 27) + bw / 2, y1, 390, y2 + 53)
    arrow(d, 329, y2 + 26, 258, y2 + 26)
    arrow(d, 164, y2 + 26, 121, y2 + 26)
    box(d, 330, 0, 120, 28, "Alerts / work orders\n-> facility team", fill="#fdeae0", stroke="#c2410c", size=7.5)
    arrow(d, 390, y2, 390, 29, color="#c2410c")
    d.add(String(0, 112, "Every interval: device -> gateway -> ingest", fontName="Arial", fontSize=7.5,
                 fillColor=colors.HexColor("#5d6f65")))
    d.add(String(0, 100, "On request: dashboard <- API <- services <- store", fontName="Arial", fontSize=7.5,
                 fillColor=colors.HexColor("#5d6f65")))
    return d


def er_diagram():
    w, h = 450, 290
    d = Drawing(w, h)

    def entity(x, y, name, fields, width=128):
        rows = len(fields)
        height = 16 + rows * 11 + 4
        d.add(Rect(x, y - height, width, height, fillColor=colors.white, strokeColor=GREEN, strokeWidth=0.9))
        d.add(Rect(x, y - 16, width, 16, fillColor=GREEN, strokeColor=GREEN))
        d.add(String(x + 6, y - 12, name, fontName="Arial-B", fontSize=8.5, fillColor=colors.white))
        for i, f in enumerate(fields):
            d.add(String(x + 6, y - 27 - i * 11, f, fontName="Arial", fontSize=7.3,
                         fillColor=colors.HexColor("#15241c")))
        return (x, y, width, height)

    g = entity(0, 290, "Gateway", ["PK id", "name, key (secret)", "last_seen"])
    m = entity(160, 290, "Meter", ["PK id", "FK building, FK gateway", "serial, kind, source", "unit, max_value",
                                   "last_reading_at"])
    r = entity(320, 290, "Reading", ["PK id", "FK meter", "timestamp, value", "interval_minutes", "quality flag"])
    e = entity(0, 185, "EnvReading", ["PK id", "FK building", "temperature, humidity", "co2_ppm, occupancy"])
    b = entity(160, 185, "Building", ["PK id", "code, name, type", "area_m2, occupants", "latitude, longitude"])
    a = entity(320, 185, "Alert", ["PK id", "FK building, FK meter", "type, severity, status", "excess, cost",
                                   "FK assigned_to (User)"])
    entity(0, 85, "EmissionFactor", ["PK id", "activity, scope, value", "valid_from, version", "source"])
    entity(160, 85, "Fuel / Waste logs", ["PK id", "date, category", "quantity / weight", "FK building"])
    entity(320, 85, "User / Commute", ["User: role, department", "CommuteSurvey: FK user,", "mode, distance, days"])

    def link(x1, y1, x2, y2, label="1 : N", dx=4, dy=3):
        d.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#5d6f65"), strokeWidth=0.9))
        d.add(String((x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy, label, fontName="Arial", fontSize=6.8,
                     fillColor=colors.HexColor("#5d6f65")))

    link(128, 262, 160, 262, dx=-10, dy=4)          # gateway -> meters
    link(288, 262, 320, 262, dx=-10, dy=4)          # meter -> readings
    link(224, 185, 224, 215)                        # building -> meters
    link(160, 150, 128, 150, dx=-10, dy=4)          # building -> environment readings
    link(288, 150, 320, 150, dx=-10, dy=4)          # building -> alerts
    link(275, 215, 345, 185, dx=6, dy=0)            # meter -> alerts
    link(224, 121, 224, 85)                         # building -> logs
    link(384, 110, 384, 85, "1 : N (assigned)")     # user -> alerts
    return d


# ------------------------------------------------------------------ document

def roman(n):
    vals = [(10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


class ReportDoc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=A4, leftMargin=2.7 * cm, rightMargin=2 * cm, topMargin=2.2 * cm,
                         bottomMargin=2.2 * cm, title=TITLE, author="Yajat M Rawal, S Surendar, Surya Swaminathan, "
                         "Shivraj Singh", subject="21CSC203P Advanced Programming Practice project report")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate("p", [frame], onPageEnd=self.decorate)])
        self.arabic_start = None

    def label(self, page):
        if self.arabic_start is None or page < self.arabic_start:
            return roman(page)
        return str(page - self.arabic_start + 1)

    def decorate(self, canv, doc):
        canv.saveState()
        w, h = A4
        canv.setStrokeColor(GRID)
        canv.setLineWidth(0.5)
        canv.line(self.leftMargin, 1.7 * cm, w - self.rightMargin, 1.7 * cm)
        canv.setFont("Times-I", 9.5)
        canv.setFillColor(colors.HexColor("#4a5a52"))
        canv.drawString(self.leftMargin, 1.25 * cm, TITLE)
        canv.setFont("Times", 10.5)
        canv.drawRightString(w - self.rightMargin, 1.25 * cm, self.label(doc.page))
        if self.arabic_start is not None and doc.page > self.arabic_start:
            canv.line(self.leftMargin, h - 1.6 * cm, w - self.rightMargin, h - 1.6 * cm)
            canv.setFont("Times-I", 9.5)
            canv.drawRightString(w - self.rightMargin, h - 1.45 * cm, "SRM Institute of Science and Technology, Vadapalani")
        canv.restoreState()


def story():
    c = N["overview30"]["carbon"]
    en = N["overview30"]["energy"]
    wa = N["overview30"]["water"]
    ws = N["overview30"]["waste"]
    tg = N["overview30"]["target"]
    fc = N["forecast"]
    sc = N["scenario"]
    tr = N["transport"]
    s = []

    # ---------------- acknowledgement
    s += [Anchor("toc", "ACKNOWLEDGEMENT", 0), P("ACKNOWLEDGEMENT", front_title)]
    s += [P("We express our sincere gratitude to the management of SRM Institute of Science and Technology, "
            "Vadapalani Campus, for providing the facilities and an encouraging academic environment for this work."),
          P("We are deeply grateful to <b>Dr. P. Chitra</b>, Professor and Head of the Department of Computer Science "
            "and Engineering (Emerging Technologies), for the constant support and for creating opportunities to work "
            "on problems that matter to our own campus."),
          P("We owe special thanks to our guide, <b>Dr. Arun Nehru J</b>, Assistant Professor, Department of CSE "
            "(Emerging Technologies), for the guidance, patient reviews and valuable suggestions at every stage of the "
            "project, from defining the carbon accounting boundary to evaluating the final system."),
          P("We also thank the faculty members and laboratory staff of the department, and the estate and facility "
            "teams whose descriptions of everyday campus operations shaped the alerting and work-order features."),
          P("Finally, we thank our families and friends for their encouragement throughout the course of this project."),
          Spacer(1, 30),
          P("Yajat M Rawal (RA2511030040010)<br/>S Surendar (RA2511030040005)<br/>Surya Swaminathan "
            "(RA2511030040008)<br/>Shivraj Singh (RA2511030040021)",
            ParagraphStyle("sig", parent=body, alignment=2))]

    # ---------------- abstract
    s += [PageBreak(), Anchor("toc", "ABSTRACT", 0), P("ABSTRACT", front_title)]
    s += [P("Universities and colleges behave like small cities: they consume electricity, water and fuel at scale, "
            "generate waste and move thousands of people every day, yet most institutions measure their environmental "
            "impact only once a year from utility bills. Annual figures are too late and too coarse to change "
            "behaviour or operations, and faults such as leaking tanks or air-conditioning left running overnight go "
            "unnoticed for weeks."),
          P("This project designs and implements <b>EcoSphere AI</b>, a Smart Campus Sustainability and Carbon "
            "Footprint Monitoring System. Readings from smart meters and IoT sensors are ingested through an "
            "authenticated gateway API, validated, stored and converted into greenhouse-gas emissions by a carbon "
            "engine that follows the GHG Protocol (Scope 1, 2 and 3) using version-controlled emission factors such as "
            "the CEA grid factor. An analytics layer learns each building's normal load profile and raises alerts for "
            "after-hours consumption, demand spikes, night-time water leaks, offline or stuck meters and poor indoor "
            "ventilation. A regression model forecasts daily electricity demand from the academic calendar and "
            "temperature, a benchmarking module ranks buildings by Energy Performance Index, and a scenario model "
            "estimates savings from LED retrofits, rooftop solar, set-point changes, occupancy controls and electric "
            "buses before money is spent."),
          P("The system is built entirely with free and open-source software: Python, Django REST Framework, SQLite, "
            "NumPy and ReportLab on the server, and React, TypeScript, Recharts and Leaflet in the browser. Role-based "
            "dashboards serve management, the facility team and the student community, and a reporting module produces "
            "GHG inventory PDFs and CSV exports."),
          P(f"Evaluated on a 120-day simulated dataset for a ten-building campus of 5,850 "
            f"people, the platform reported an annualised footprint of about {c['annualised_tco2e']:,.0f} tCO<sub>2</sub>e "
            f"({c['per_student_t']:.2f} t per student), detected all six injected faults with no false alarms, and "
            f"forecast daily demand with a mean absolute percentage error of {fc['mape_pct']}%. A combined package of "
            f"measures was estimated to avoid about {sc['tco2e_saved']:,.0f} tCO<sub>2</sub>e per year with a payback of "
            f"{sc['payback_years']} years. The results show that continuous monitoring can turn sustainability from an "
            "annual report into a daily operating practice."),
          Spacer(1, 8),
          P("<b>Keywords:</b> smart campus, carbon footprint, GHG Protocol, IoT, anomaly detection, energy forecasting, "
            "Django, React, sustainability dashboard.")]

    # ---------------- contents
    s += [PageBreak(), P("TABLE OF CONTENTS", front_title), ListPlaceholder("toc")]

    # ---------------- lists (filled after a first pass; see main)
    s += [PageBreak(), P("LIST OF FIGURES", front_title),
          ListPlaceholder("figures"), Spacer(1, 8), P("LIST OF TABLES", front_title), ListPlaceholder("tables"),
          Spacer(1, 8), P("LIST OF ABBREVIATIONS", front_title),
          ListPlaceholder("abbr")]

    s += [PageBreak(), Anchor("arabic", "")]

    # ================= Chapter 1
    s += chapter("Introduction")
    s += section("Background")
    s += [P("Higher-education campuses are significant contributors to local energy demand and emissions. A typical "
            "campus includes academic blocks, hostels, laboratories, libraries, canteens, sports facilities, staff "
            "housing and a vehicle fleet. In warm and humid regions such as Chennai, cooling loads make grid "
            "electricity the dominant source of emissions, and water is pumped, stored and treated on site at a "
            "further energy cost."),
          P("At the same time, campuses are well placed to lead. They have a captive population, control over their "
            "own infrastructure, research capability and an educational mission. A monitored, data-driven campus "
            "doubles as a living laboratory: the same data that helps the estate office find a leaking valve can be "
            "used by students for coursework in data science, energy systems and environmental studies."),
          P("The guiding principle of this project is simple: <i>what is measured gets managed</i>. Continuous "
            "monitoring turns sustainability from an annual compliance exercise into a daily operating practice.")]
    s += section("Problem Statement")
    s += [P("Current campus sustainability practice commonly suffers from the following gaps:")]
    s += bullets(["Energy and water are recorded at the main meter only, so individual buildings and departments are "
                  "invisible and cannot be held accountable.",
                  "Carbon accounting is manual, periodic and spreadsheet-based, which makes it slow and error-prone.",
                  "Faults such as leaks, idle air-conditioning and lights left on go unnoticed for days or weeks.",
                  "Students and staff receive no feedback on the impact of their behaviour.",
                  "Reports are hard to compare year on year because methods, factors and boundaries change."])
    s += section("Objectives")
    s += numbered(["Monitor electricity, solar generation, water, indoor environment, waste and transport data in near "
                   "real time.",
                   "Calculate campus emissions automatically using recognised, version-controlled emission factors "
                   "aligned with the GHG Protocol.",
                   "Detect anomalies and wastage and route alerts to the responsible team as trackable work orders.",
                   "Provide role-specific dashboards for management, facility staff and the campus community.",
                   "Support target setting, demand forecasting, benchmarking and what-if scenario analysis.",
                   "Build a scalable, low-cost architecture using only free and open-source software that can start "
                   "small and expand building by building."])
    s += section("Scope of the Project")
    s += [P("The system covers measurement, data transmission, storage, analytics, visualisation, alerting and "
            "reporting. It addresses Scope 1 (generators, fleet, LPG, refrigerant leakage), Scope 2 (purchased "
            "electricity, location- and market-based) and a practical subset of Scope 3 (water supply and "
            "treatment, waste disposal and student and staff commuting). It does not replace existing building "
            "management systems; it integrates with them through a documented ingestion API. Because physical meters "
            "were not available during development, a physics-based simulator generates realistic sensor data so that "
            "every layer of the system can be exercised end to end.")]
    s += section("Organisation of the Report")
    s += [P("Chapter 2 reviews the standards and existing approaches that informed the design. Chapter 3 lists the "
            "functional and non-functional requirements. Chapter 4 presents the system architecture, data flow and "
            "database design, and Chapter 5 explains the carbon accounting method and the analytical algorithms. "
            "Chapter 6 describes the implementation, Chapter 7 discusses the results, Chapter 8 covers testing, and "
            "Chapters 9 and 10 present limitations, future enhancements and conclusions.")]

    # ================= Chapter 2
    s += chapter("Literature Survey and Standards")
    s += section("Carbon Accounting Standards")
    s += [P("The <b>GHG Protocol Corporate Accounting and Reporting Standard</b> is the most widely used framework for "
            "organisational inventories. It classifies emissions into three scopes and requires the organisation to "
            "define its boundary (operational or financial control) and a base year against which progress is "
            "measured. Its Scope 2 guidance requires dual reporting: a <i>location-based</i> figure using the average "
            "grid factor and a <i>market-based</i> figure that reflects contractual purchases of renewable power."),
          P("<b>ISO 14064-1</b> specifies principles for quantifying and reporting GHG emissions and removals, while "
            "<b>ISO 50001</b> defines energy-management systems built around Energy Performance Indicators (EnPIs) and "
            "baselines. For India, the <b>Central Electricity Authority (CEA) CO<sub>2</sub> Baseline Database</b> "
            "publishes the grid emission factor, recently in the region of 0.7-0.8 kg CO<sub>2</sub>/kWh; because the "
            "value is revised periodically, a monitoring system must store factors as dated, versioned parameters.")]
    s += section("Campus Sustainability Rating Systems")
    s += [P("Green-building rating systems such as <b>GRIHA</b> and <b>IGBC</b> assess energy performance (kWh/m<super>2</super>/year), "
            "water efficiency, waste management and renewable energy. <b>AASHE STARS</b>, used by universities "
            "worldwide, adds operations, engagement and curriculum credits, and NIRF-style disclosures in India "
            "increasingly ask for sustainability data. All of them reward measured, verifiable data over estimates."),
          P("The UN Sustainable Development Goals most relevant to this work are SDG 7 (affordable and clean energy), "
            "SDG 11 (sustainable cities), SDG 12 (responsible consumption) and SDG 13 (climate action).")]
    s += section("Existing Approaches")
    s.extend(table([
        ["Approach", "Strengths", "Limitations"],
        ["Annual utility-bill audit", "Cheap, credible totals", "No building detail; results arrive months late"],
        ["Building Management System (BMS)", "Real-time control of HVAC", "Vendor-specific; no carbon accounting or "
                                                                          "community view; expensive licences"],
        ["Commercial energy dashboards", "Polished visualisation", "Subscription cost; electricity only; data held by "
                                                                   "vendor"],
        ["Spreadsheet carbon calculators", "Flexible, familiar", "Manual, error-prone, no alerts, poor versioning"],
        ["<b>Proposed system</b>", "Integrated multi-resource monitoring, GHG engine, alerts, forecasting and "
                                   "engagement; free software", "Requires metering investment for real deployment"],
    ], [4.2 * cm, 5.4 * cm, 6.2 * cm], "Comparison of existing approaches with the proposed system"))
    s += section("Analytical Techniques")
    s += [P("Research on building energy analytics shows that simple, explainable models perform well for campus "
            "loads, which are driven mainly by occupancy schedules and weather. Robust statistics such as the median "
            "and median absolute deviation (MAD) are widely recommended for anomaly detection because, unlike the mean "
            "and standard deviation, they are not distorted by the very anomalies being sought. Night-time minimum "
            "flow analysis is the standard method used by water utilities to detect leaks, and multiple linear "
            "regression with calendar and temperature terms is a common baseline for short-term demand forecasting. "
            "These findings guided the choice of transparent algorithms that can be explained, audited and run on "
            "modest hardware.")]

    # ================= Chapter 3
    s += chapter("Requirements Analysis")
    s += section("Stakeholders and Roles")
    s.extend(table([
        ["Role", "Typical users", "Capabilities"],
        ["Administrator", "Sustainability officer, management", "All dashboards; campus settings and boundary; "
                                                                 "emission factors; targets; buildings, meters and "
                                                                 "gateways; user roles"],
        ["Facility team", "Estate office, electricians, plumbers", "Operations console; acknowledge and resolve "
                                                                    "alerts; run anomaly scans; log fuel, refrigerant "
                                                                    "and waste"],
        ["Community", "Students and staff", "Read-only dashboards; hostel and department leaderboards; private "
                                            "commute footprint calculator"],
    ], [3 * cm, 4.6 * cm, 8.2 * cm], "User roles and access rights"))
    s += section("Functional Requirements")
    s.extend(table([
        ["ID", "Requirement"],
        ["FR1", "Ingest meter readings from authenticated gateways; reject malformed data and flag out-of-range values."],
        ["FR2", "Convert activity data to kg CO<sub>2</sub>e by scope, source, building and period using the factor "
                "valid on each day."],
        ["FR3", "Show campus KPIs: total and per-student emissions, kWh/m<super>2</super>, renewable share, water per "
                "person, waste diversion and progress to target."],
        ["FR4", "Detect after-hours load, spikes, leaks, stuck or offline meters and high CO<sub>2</sub>, and create "
                "de-duplicated alerts with estimated cost."],
        ["FR5", "Allow alerts to be acknowledged, annotated, assigned and resolved (work-order tracking)."],
        ["FR6", "Forecast daily electricity demand, emissions and cost with a prediction interval."],
        ["FR7", "Benchmark buildings and model the savings, cost and payback of interventions."],
        ["FR8", "Record waste weighings, fuel and refrigerant use, trees and commute surveys."],
        ["FR9", "Generate a GHG inventory PDF and CSV exports for any date range."],
        ["FR10", "Register users, authenticate with tokens and enforce role-based permissions."],
    ], [1.6 * cm, 14.2 * cm], "Functional requirements"))
    s += section("Non-Functional Requirements")
    s += bullets(["<b>Cost:</b> every component must be free and open source; no paid APIs or cloud subscriptions.",
                  "<b>Security:</b> hashed passwords, JWT access tokens with refresh rotation, per-gateway device keys, "
                  "role-based authorisation and rate limiting on public endpoints.",
                  "<b>Data integrity:</b> suspicious values are flagged, never silently corrected or deleted; factor "
                  "history is append-only so past results remain reproducible.",
                  "<b>Privacy:</b> commute answers are visible only to the person who submitted them; only aggregated "
                  "totals are reported.",
                  "<b>Performance:</b> dashboard queries should return in under one second for a year of hourly data "
                  "on a laptop.",
                  "<b>Usability and portability:</b> responsive interface for desktop and mobile; runs on Windows, "
                  "Linux or macOS with a one-step setup."])
    s += section("Hardware and Software Requirements")
    s.extend(table([
        ["Layer", "Choice (all free)", "Purpose"],
        ["Backend language", "Python 3.12", "Services, analytics and management commands"],
        ["Web framework", "Django 5.2, Django REST Framework 3.17", "REST API, ORM, admin site"],
        ["Authentication", "djangorestframework-simplejwt", "JSON Web Tokens with refresh rotation"],
        ["Database", "SQLite (PostgreSQL/TimescaleDB ready)", "Readings, metadata, factors and logs"],
        ["Numerics and reports", "NumPy, ReportLab", "Regression forecasting; PDF generation"],
        ["Frontend", "React 19, TypeScript, Vite", "Single-page application"],
        ["UI libraries", "TanStack Query, Zustand, Recharts, Leaflet + OpenStreetMap", "Data fetching, state, "
                                                                                      "charts, campus map"],
        ["Hardware (deployment)", "ESP32 boards, Modbus meters, ultrasonic flow meters", "Low-cost sensing"],
        ["Development machine", "Any PC with 4 GB RAM", "Runs all services locally"],
    ], [3.6 * cm, 6.4 * cm, 5.8 * cm], "Technology stack"))

    # ================= Chapter 4
    s += chapter("System Design")
    s += section("Layered Architecture")
    s += [P("The system follows the five-layer architecture proposed in the project report. Each layer has a single "
            "responsibility and communicates with its neighbours through well-defined interfaces, so that, for "
            "example, a simulated meter can be replaced by a real Modbus meter without any change above the "
            "connectivity layer.")]
    s.append(drawing_figure(architecture_diagram(), "Five-layer architecture of the system"))
    s += bullets(["<b>Sensing:</b> energy meters at each building incomer, rooftop solar meters, water meters per "
                  "building and per source, indoor environment sensors, a weather station, waste scales and fleet logs.",
                  "<b>Connectivity:</b> edge gateways buffer readings during outages and forward them over HTTP with a "
                  "secret key; MQTT or LoRaWAN can be bridged through the same adapter.",
                  "<b>Data platform:</b> validation, quality flags, time-series storage and aggregation to hourly, "
                  "daily and monthly values; metadata such as buildings, tariffs and factors in relational tables.",
                  "<b>Analytics:</b> carbon engine, anomaly detection, forecasting, benchmarking and scenario modelling.",
                  "<b>Application:</b> management dashboard, operations console, community portal and reporting."])
    s += section("Data Flow")
    s += [P("Figure 4.2 shows how a reading travels through the system. Devices push readings to the gateway, which "
            "authenticates with the ingestion endpoint. Valid readings are stored; out-of-range readings are stored "
            "with a <i>suspect</i> flag and excluded from totals. Analytics services read the store on demand when a "
            "dashboard calls the REST API, and a periodic scan writes alerts that appear in the operations console.")]
    s.append(drawing_figure(dataflow_diagram(), "Data flow from device to dashboard"))
    s += section("Database Design")
    s += [P("The relational schema separates the physical campus (buildings, gateways, meters), measurements "
            "(readings, indoor environment, weather), logged activity data (fuel, waste, commuting, trees), "
            "configuration (emission factors, targets, calendar, campus settings) and operations (alerts, users). "
            "Readings are indexed on (meter, timestamp) so that hourly and daily aggregation stays fast.")]
    s.append(drawing_figure(er_diagram(), "Simplified entity-relationship diagram"))
    s += section("API Design")
    s += [P("All functionality is exposed through a versionable REST API under <font name='Cour'>/api/</font>. "
            "The main endpoints are listed below; further CRUD endpoints exist for buildings, meters, gateways, factors, logs, trees, targets and users.")]
    s.extend(table([
        ["Endpoint", "Method", "Description"],
        ["/api/auth/login/, /refresh/, /register/", "POST", "Obtain and rotate JWT tokens; self-registration"],
        ["/api/ingest/", "POST", "Gateway ingestion (X-Gateway-Key header)"],
        ["/api/analytics/overview/", "GET", "Campus KPIs, scope split, monthly trend, target progress"],
        ["/api/analytics/live/", "GET", "Current demand, solar, water flow and indoor status per building"],
        ["/api/analytics/forecast/", "GET", "Demand forecast with 95% interval and model metrics"],
        ["/api/analytics/scenarios/", "POST", "Savings, cost and payback for chosen interventions"],
        ["/api/alerts/{id}/", "PATCH", "Acknowledge, assign, annotate or resolve an alert"],
        ["/api/reports/ghg.pdf", "GET", "GHG inventory report for a date range"],
    ], [6.2 * cm, 1.7 * cm, 7.9 * cm], "Key REST API endpoints", font=10))
    s += section("Security Design")
    s += [P("Passwords are stored with Django's PBKDF2 hasher. Users authenticate once and receive a short-lived "
            "access token (30 minutes) and a refresh token (7 days) that is rotated on use. Every API view declares a "
            "permission class: read-only for all signed-in users, write access restricted to administrators or "
            "facility staff as appropriate. Devices never use user accounts; each gateway has its own random 160-bit "
            "key that can be revoked independently. Anonymous endpoints are rate-limited, and administrators cannot "
            "remove their own privileges by mistake.")]

    # ================= Chapter 5
    s += chapter("Methodology and Algorithms")
    s += section("Carbon Accounting Method")
    s += [P("Every emission line is calculated with the basic relationship of the GHG Protocol:"),
          P("E<sub>d</sub> (kg CO<sub>2</sub>e) = A<sub>d</sub> × EF<sub>d</sub>", eq),
          P("where A<sub>d</sub> is the activity data on day <i>d</i> (kWh, litres, kg, kL or passenger-km) and "
            "EF<sub>d</sub> is the emission factor whose <i>valid_from</i> date is the latest on or before <i>d</i>. "
            "Applying factors day by day means that publishing a new CEA value changes only the days after it takes "
            "effect, and every historical report can be reproduced exactly. Market-based Scope 2 is computed as the "
            "location-based value multiplied by (1 - certified green power share)."),
          P("Commuting is estimated from anonymous surveys. For respondents <i>i</i> using mode <i>m</i>, the daily "
            "passenger-km scaled to the whole population P from n responses is:"),
          P("km<sub>m</sub> = (P / n) × (44 / 52) × Σ<sub>i in m</sub> 2 · dist<sub>i</sub> · days<sub>i</sub> / 7", eq),
          P("where 44/52 spreads the academic year over the calendar. Tree sequestration is calculated separately and "
            "never subtracted from emissions, following the conservative approach recommended in the project report.")]
    s.extend(table([
        ["Activity", "Scope", "Factor", "Source (indicative)"],
        ["Grid electricity", "2", "0.716 kg/kWh (v2, from Apr 2025)", "CEA CO<sub>2</sub> Baseline Database"],
        ["Diesel (generators, buses)", "1", "2.68 kg/L", "IPCC 2006 / DEFRA"],
        ["LPG (canteen, labs)", "1", "2.98 kg/kg", "IPCC 2006"],
        ["Refrigerant R-410A / R-32", "1", "2088 / 675 kg/kg", "IPCC AR4 GWP-100"],
        ["Water supply and treatment", "3", "0.344 kg/kL", "DEFRA (indicative)"],
        ["Waste to landfill / recycled / composted", "3", "0.497 / 0.021 / 0.009 kg/kg", "DEFRA (indicative)"],
        ["Commute: car / two-wheeler / bus / metro", "3", "0.171 / 0.083 / 0.105 / 0.035 kg/km", "DEFRA, indicative"],
    ], [5 * cm, 1.5 * cm, 4.8 * cm, 4.5 * cm], "Default emission factors (to be confirmed before disclosure)",
        font=10))
    s += section("Anomaly Detection")
    s += [P("For every electricity meter, the normal profile is learnt separately for each hour of the day and for "
            "working and non-working days (weekends, holidays and vacations from the academic calendar) over the "
            "previous 28 days. For a recent hourly value x with historical values H in the same bucket, a robust "
            "z-score is computed:"),
          P("z = (x - median(H)) / max(1.4826 · MAD(H), 0.05 · median(H), 1)", eq),
          P("An hour is flagged when z &gt; 4 and the excess exceeds both 20% of the median and 25 kWh, which "
            "suppresses alarms on tiny loads. Flagged hours are grouped by building and operational date (hours after "
            "midnight belong to the previous evening). Groups between 22:00 and 06:00 in non-residential buildings "
            "become <i>after-hours</i> alerts; others become <i>spike</i> alerts. Severity is graded on the excess "
            "energy, and the estimated cost is excess × tariff."),
          P("<b>Leak detection</b> uses the minimum hourly flow between 01:00 and 05:00, when legitimate use is close to "
            "zero. If the minimum on a recent night exceeds max(2.5 × baseline, baseline + 0.5 kL/h), where the "
            "baseline is the median of the previous four weeks' night minima, one continuing leak work order is "
            "opened for that meter."),
          P("<b>Data-quality checks</b> raise alerts for six identical non-zero readings (stuck sensor), meters silent "
            "for more than three hours (offline) and readings above the meter's physical limit (impossible value). "
            "<b>Indoor environment</b> alerts are raised when CO<sub>2</sub> exceeds 1200 ppm. Every alert carries a "
            "unique de-duplication key, so repeated scans never create duplicates.")]
    s += section("Demand Forecasting")
    s += [P("Daily grid electricity y<sub>t</sub> is modelled by multiple linear regression fitted with NumPy least "
            "squares on the last 120 days:"),
          P("y<sub>t</sub> = β<sub>0</sub> + β<sub>1</sub>·t + Σ<sub>k=1..6</sub> γ<sub>k</sub>·DOW<sub>k</sub> + "
            "δ·Holiday<sub>t</sub> + θ·(T<sub>t</sub> - 28) + ε<sub>t</sub>", eq),
          P("where DOW are day-of-week indicators (Sunday as reference), Holiday marks weekday holidays and vacations, "
            "and T is the mean outdoor temperature. The coefficient θ directly gives the cooling sensitivity in kWh "
            "per degree. Future days use the calendar and the recent average temperature; the 95% prediction interval "
            "is ±1.96σ of the residuals. Accuracy is reported as MAPE and R<super>2</super>.")]
    s += section("Benchmarking and Scenario Modelling")
    s += [P("Buildings are compared on the Energy Performance Index, EPI = annualised kWh / floor area (m<super>2</super>), "
            "together with kWh and litres of water per occupant per day. Star bands are modelled on BEE building "
            "rating ranges."),
          P("The scenario model starts from annualised grid consumption E (from the last 30 days) and applies "
            "transparent engineering assumptions that the user can change: LED retrofit saves 50% of the lighting "
            "share (20% of E) for the retrofitted fraction; rooftop solar yields 1400 kWh per kWp per year; each "
            "1 °C increase in AC set-point saves 6% of the cooling share (45% of E); occupancy controls save 15% of "
            "cooling and lighting in covered areas; an electric bus replaces diesel at 4 km/L but adds 1.1 kWh/km of "
            "charging. For each measure the model reports kWh and diesel saved, tCO<sub>2</sub>e avoided, annual "
            "saving, capital cost and simple payback = capex / annual saving.")]

    # ================= Chapter 6
    s += chapter("Implementation")
    s += section("Project Structure")
    s += [P("The backend is a Django project with four applications. <b>accounts</b> holds the custom user model "
            "with roles, registration and permission classes. <b>monitoring</b> models buildings, gateways, meters, "
            "readings, indoor and weather data, the academic calendar and alerts, and implements the ingestion "
            "endpoint. <b>sustainability</b> stores emission factors, fuel and refrigerant logs, waste weighings, "
            "commute surveys, trees and targets. <b>analytics</b> contains the services described in Chapter 5, the "
            "REST views, and two management commands: <font name='Cour'>seed_demo</font>, which builds a realistic "
            "campus with 120 days of hourly history, and <font name='Cour'>simulate</font>, which acts as a live "
            "gateway. The frontend is a React and TypeScript single-page application organised into pages, shared "
            "components, an API client and small state stores.")]
    s += section("Carbon Engine")
    s += [P("The <font name='Cour'>FactorBook</font> class loads every factor version once and answers which value "
            "applied on a given day; the engine then produces one line item per building, day and activity. All "
            "dashboards, the PDF report and the CSV export are computed from the same line items, which guarantees "
            "that the numbers agree everywhere.")]
    s.append(Preformatted('''class FactorBook:
    """Loads every factor version once; answers 'which value applied on this day?'."""
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
        return chosen''', code))
    s += section("IoT Ingestion and Simulation")
    s += [P("Gateways post batches of up to 5000 readings to <font name='Cour'>/api/ingest/</font>. Each reading "
            "carries the meter serial, the consumption during the interval and optionally the interval length and "
            "timestamp. The endpoint authenticates the gateway key, rejects unknown meters, non-numeric or future "
            "values with a per-item error, flags values above the meter's hourly limit as suspect, stores the rest in "
            "one bulk insert and updates each meter's last-seen time.")]
    s.append(Preformatted('''POST /api/ingest/        X-Gateway-Key: 6e73...bc69
{"readings": [{"serial": "EM-ACA", "value": 42.5, "interval_minutes": 15},
              {"serial": "WM-BH1", "value": 0.61, "interval_minutes": 15}]}
-> 201 {"accepted": 2, "rejected": []}''', code))
    s += [P("Because physical meters were not available, the simulator models each building from first principles: "
            "an always-on base load, an occupancy-driven load that follows the timetable of its building type, and a "
            "cooling load proportional to the outdoor temperature above 24 °C. Solar output follows irradiance with "
            "day-to-day cloud cover, water use follows daily routines, and the weather is Chennai-like with monsoon "
            "rain in October. Day-level randomness is seeded by date, so historical and live data agree. The seed "
            "command deliberately injects six faults (air-conditioning left on for two nights, a hostel tank leak, a "
            "lab test rig left on, a poorly ventilated hall and an impossible meter value) to validate detection.")]
    s += section("User Interface")
    s += [P("The web application provides thirteen screens grouped into Overview, Modules, Intelligence and "
            "Administration. Server state is cached with TanStack Query; the live console refreshes every 30 seconds. "
            "Charts use Recharts and the campus map uses Leaflet with free OpenStreetMap tiles. The layout adapts to "
            "mobile screens, and pages are code-split so that the initial download stays small.")]


    s.append(figure(FIG / "shot_dashboard.jpg", "Management dashboard with KPIs, monthly scope trend and target "
                                                "reference lines", width=12.5 * cm))
    s.append(figure(FIG / "shot_operations.jpg", "Operations console: live building status, IoT health and campus "
                                                 "map", width=12.5 * cm))



    # ================= Chapter 7
    s += chapter("Results and Discussion")
    s += section("Campus Footprint")
    s += [P(f"Table 7.1 summarises the key performance indicators reported by the system for the most recent 30 days "
            f"of the evaluation dataset (ten buildings, 65,500 m<super>2</super>, 5,200 students and 650 staff).")]
    s.extend(table([
        ["Indicator", "Value", "Indicator", "Value"],
        ["Total emissions (30 days)", f"{c['total_tco2e']:,.1f} tCO<sub>2</sub>e", "Renewable share of electricity",
         f"{en['renewable_share_pct']}%"],
        ["Annualised emissions", f"{c['annualised_tco2e']:,.0f} tCO<sub>2</sub>e/yr", "Energy Performance Index",
         f"{en['eui_kwh_m2_yr']} kWh/m<super>2</super>/yr"],
        ["Per student", f"{c['per_student_t']:.2f} t/yr", "Peak demand", f"{en['peak_demand']['kw']:,.0f} kW"],
        ["Per floor area", f"{c['per_m2_kg']} kg/m<super>2</super>/yr", "Water use",
         f"{wa['litres_per_person_day']} L/person/day"],
        ["Scope 1 / 2 / 3", f"{c['scope1_t']} / {c['scope2_t']} / {c['scope3_t']} t", "Recycled + harvested water",
         f"{wa['recycled_harvested_pct']}%"],
        ["Electricity cost (30 days)", f"Rs. {en['cost_inr'] / 1e5:,.1f} lakh", "Waste diversion rate",
         f"{ws['diversion_rate_pct']}%"],
        ["Tree sequestration", f"{c['sequestration_t_per_year']} tCO<sub>2</sub>/yr", "Sustainable commute share",
         f"{N['overview30']['transport']['sustainable_share_pct']}%"],
    ], [4.4 * cm, 3.6 * cm, 4.4 * cm, 3.4 * cm], "Campus KPIs reported by the system (last 30 days)", font=10))
    s += [P(f"Purchased electricity dominates the footprint at about {c['scope2_t'] / c['total_tco2e'] * 100:.0f}% of "
            f"the total, as expected for a cooling-dominated campus in South India, followed by student and staff "
            f"commuting. Direct Scope 1 sources are small, but refrigerant leakage stands out: a single 6 kg R-410A "
            f"top-up equals about 12.5 tCO<sub>2</sub>e, more than a month of the entire bus fleet. Tree "
            f"sequestration offsets only about {c['sequestration_t_per_year'] / c['annualised_tco2e'] * 100:.2f}% of "
            f"annual emissions, which confirms that planting is not a substitute for reducing consumption.")]
    s.append(figure(FIG / "fig_sources.png", "Emissions by source over the last 30 days"))
    s += section("Energy Use Patterns")
    s += [P("Building-level metering reveals patterns that a single main meter hides. Academic blocks and laboratories "
            "follow the timetable, with laboratories retaining a high base load from equipment; hostels peak in the "
            "evening; the food court shows breakfast, lunch and dinner peaks. Rooftop solar on Academic Block A "
            "visibly shaves the midday grid draw.")]
    s.append(figure(FIG / "fig_load_profile.png", "Average working-day load profile by building type"))
    s.append(figure(FIG / "fig_grid_solar.png", "Grid draw and rooftop solar generation, Academic Block A"))
    s += section("Fault Detection")
    s += [P("The anomaly scan raised exactly six alerts on the evaluation dataset, one for each injected fault, with "
            "no false positives on the 120 days of normal data. Figure 7.4 shows the after-hours alert for Academic "
            "Block B: night-time load rose from about 50 kWh to over 200 kWh per hour for two nights while the learnt "
            "profile stayed flat, an excess of roughly 1,290 kWh (about Rs. 11,600) per night. Figure 7.5 shows the "
            "leak signature in Boys Hostel 1, where minimum night flow jumped from about 0.2 to 2.6 kL/h, an estimated "
            "loss of 58 kL per day. In a manual, bill-based process such faults would typically surface only weeks "
            "later.")]
    s.append(figure(FIG / "fig_anomaly.png", "After-hours air-conditioning load detected in Academic Block B"))
    s.append(figure(FIG / "fig_leak.png", "Night-time minimum flow revealing a leak in Boys Hostel 1"))
    s.extend(table([
        ["Injected fault", "Detected as", "Severity", "Estimated impact"],
        ["AC left on overnight (two nights), Academic Block B", "After-hours load x2", "High", "~1,290 kWh per night"],
        ["Leaking tank float valve, Boys Hostel 1", "Possible water leak", "High", "~58 kL per day"],
        ["Test rig left at full power, Tech Park Labs", "Electricity spike", "High", "~780 kWh"],
        ["Packed hall with fresh air off, Central Library", "Poor ventilation", "Medium", "CO<sub>2</sub> ~1,490 ppm"],
        ["99,999 kWh reading, Administration Block", "Impossible value", "Low", "Flagged, excluded"],
    ], [6.2 * cm, 3.6 * cm, 1.9 * cm, 4.1 * cm], "Detection results for injected faults", font=10))
    s += section("Forecasting Accuracy")
    s += [P(f"The regression model was trained on {fc['training_days']} days and achieved a mean absolute percentage "
            f"error of {fc['mape_pct']}% and R<super>2</super> of {fc['r2']}. It captures the weekly cycle, the lower "
            f"demand during holidays and vacations, and a cooling sensitivity of about "
            f"{fc['temperature_sensitivity_kwh_per_c']:,.0f} kWh per day for each additional degree Celsius. The 30-day "
            f"forecast predicts {fc['kwh'] / 1000:,.0f} MWh, {fc['tco2e']:,.0f} tCO<sub>2</sub>e and a bill of about "
            f"Rs. {fc['cost'] / 1e5:,.1f} lakh, which supports budgeting and peak-load planning.")]
    s.append(figure(FIG / "fig_forecast.png", "Actual, fitted and forecast daily grid electricity"))
    s += section("Benchmarking")
    s += [P(f"The food court has the highest Energy Performance Index ({N['benchmark'][-1][1]:.0f} kWh/m<super>2</super>/yr) "
            f"because of cooking and refrigeration in a small floor area, followed by Tech Park Labs "
            f"({N['benchmark'][-2][1]:.0f}). The sports complex is the most efficient. Normalising by area and "
            "occupancy makes such comparisons fair and points retrofit budgets at the right buildings.")]
    s.append(figure(FIG / "fig_benchmark.png", "Energy Performance Index by building"))
    s += section("Waste, Transport and Engagement")
    s += [P(f"The waste module shows a diversion rate of {N['waste']['diversion_rate_pct']}%, with 80% of organic "
            f"waste composted or converted to biogas, and the weekly trend in Figure 7.8 reflects the improvement "
            f"from a segregation drive. Diverting waste from landfill avoided about {N['waste']['avoided_tco2e']} "
            f"tCO<sub>2</sub>e over the period. Commute surveys show {tr['sustainable_share_pct']:.0f}% of trips by "
            f"walking, cycling, bus, metro or electric two-wheeler, yet commuting still contributes about "
            f"{tr['commute_annual_tco2e']:,.0f} tCO<sub>2</sub>e per year, mostly from cars and petrol two-wheelers. "
            "The hostel leaderboard converts week-on-week reductions into points, giving residents visible feedback.")]
    s.append(figure(FIG / "fig_waste_commute.png", "Weekly waste diversion rate and commute mode share"))
    s += section("Scenario Analysis")
    rows = [["Measure", "tCO<sub>2</sub>e/yr", "Saving/yr", "Capex", "Payback"]]
    for name, t, save, capex, pb in sc["measures"]:
        rows.append([name, f"{t:,.0f}", f"Rs. {save / 1e5:,.1f} L", f"Rs. {capex / 1e5:,.1f} L" if capex else "Nil",
                     "Immediate" if pb == 0 else f"{pb} yr"])
    rows.append(["<b>Total</b>", f"<b>{sc['tco2e_saved']:,.0f}</b>", f"<b>Rs. {sc['annual_saving_inr'] / 1e5:,.1f} L</b>",
                 f"<b>Rs. {sc['capex_inr'] / 1e5:,.1f} L</b>", f"<b>{sc['payback_years']} yr</b>"])
    s.extend(table(rows, [6.3 * cm, 2.3 * cm, 2.6 * cm, 2.6 * cm, 2 * cm],
                   "Scenario: 50% LED retrofit, 250 kWp solar, +1 °C set-point, 30% occupancy controls, 2 e-buses",
                   font=10))
    s += [P(f"The combined package would cut grid electricity by {sc['electricity_reduction_pct']}% and avoid about "
            f"{sc['tco2e_saved']:,.0f} tCO<sub>2</sub>e per year with a payback of {sc['payback_years']} years. Raising "
            "air-conditioning set-points costs nothing, and LED retrofits and occupancy controls pay back in about a "
            "year. The model also exposes a counter-intuitive result: on today's coal-heavy grid, electric buses save "
            "money but slightly <i>increase</i> emissions unless they are charged from solar, an insight that would be "
            "easy to miss without quantitative modelling.")]

    # ================= Chapter 8
    s += chapter("Testing and Validation")
    s += section("Testing Strategy")
    s += [P("Testing combined automated end-to-end tests, manual interface testing for every role and screen, and "
            "data validation against known inputs. The automated suite seeds a fresh 45-day campus in an isolated "
            "test database and exercises the carbon engine, anomaly detection, ingestion, permissions and every "
            "analytics endpoint. The frontend is type-checked by the TypeScript compiler on every build.")]
    s += section("Test Cases")
    s.extend(table([
        ["#", "Test case", "Expected result", "Status"],
        ["1", "Electricity line item equals kWh × 0.716", "Exact match for every building-day", "Pass"],
        ["2", "New factor version from a given date", "Old value before, new value after", "Pass"],
        ["3", "Suspect 99,999 kWh reading", "Excluded from totals", "Pass"],
        ["4", "All three scopes present in 30-day inventory", "Scopes 1, 2 and 3 reported", "Pass"],
        ["5", "Injected faults", "After-hours, spike, leak, CO<sub>2</sub> and impossible-value alerts", "Pass"],
        ["6", "Repeated anomaly scan", "No duplicate alerts", "Pass"],
        ["7", "Ingest batch with bad items", "2 accepted, 2 rejected with reasons, 1 flagged", "Pass"],
        ["8", "Ingest with wrong gateway key", "HTTP 401", "Pass"],
        ["9", "Login and profile", "Token issued; role returned", "Pass"],
        ["10", "Anonymous access to analytics", "HTTP 401", "Pass"],
        ["11", "Student writes factors, logs, alerts, users", "HTTP 403 for each", "Pass"],
        ["12", "Facility resolves an alert", "Status resolved, timestamp set", "Pass"],
        ["13", "Administrator demotes self", "HTTP 400, refused", "Pass"],
        ["14", "Commute answers privacy", "User sees only own answers", "Pass"],
        ["15", "All 16 analytics/report endpoints", "HTTP 200", "Pass"],
        ["16", "Invalid date ranges and datasets", "HTTP 400 with message", "Pass"],
        ["17", "14-day forecast", "14 points, MAPE below 10%", "Pass"],
        ["18", "GHG report download", "Valid PDF document", "Pass"],
    ], [0.8 * cm, 6.2 * cm, 7 * cm, 1.8 * cm], "Automated test cases (18 of 18 passing)", font=9.8))
    s += section("Performance and Usability")
    s += [P("With about 78,000 hourly readings, the campus overview endpoint responds in about 0.2 s, a year-to-date "
            "overview in under 1 s and the GHG PDF in about 1 s on an ordinary laptop. Seeding 120 days of data takes "
            "about seven seconds. Manual tests confirmed that each role sees only the navigation and actions it is "
            "allowed, that the live console updates as the simulator streams readings, that forms validate input "
            "and show clear error messages, and that the layout works without horizontal scrolling on a 375-pixel "
            "mobile screen.")]

    # ================= Chapter 9
    s += chapter("Challenges and Future Enhancements")
    s += section("Challenges and Mitigation")
    s.extend(table([
        ["Challenge", "Mitigation adopted"],
        ["High upfront cost of metering", "Free software stack; phased, building-by-building rollout; ESP32-class "
                                          "low-cost sensing where accuracy needs are modest"],
        ["Legacy and incompatible meters", "Gateway adapter pattern; simple HTTP ingestion that any device can call"],
        ["Poor data quality", "Validation, suspect flags, stuck/offline checks, completeness KPIs, cross-checks with "
                              "utility bills"],
        ["Changing emission factors", "Dated, versioned factor register; append-only history"],
        ["Privacy of personal travel data", "Anonymous aggregation; individuals see only their own answers"],
        ["Low community engagement", "Leaderboards, points, personal footprint and practical tips"],
    ], [5 * cm, 10.8 * cm], "Challenges and mitigation"))
    s += section("Limitations")
    s += bullets(["The evaluation uses simulated data; accuracy must be re-validated against real meters and bills "
                  "during a pilot.",
                  "Default emission factors are indicative and must be replaced with the latest official values.",
                  "SQLite suits a pilot; a campus-wide deployment with minute-level data should move to PostgreSQL "
                  "with TimescaleDB, which the ORM supports without code changes.",
                  "Scope 3 excludes purchased goods and business travel."])
    s += section("Future Enhancements")
    s += bullets(["AI-assisted control that adjusts air-conditioning set-points and lighting automatically from "
                  "occupancy and weather.",
                  "A digital twin of the campus for testing interventions virtually.",
                  "Native MQTT and LoRaWAN adapters and WebSocket push for sub-minute live views.",
                  "Integration with an internal carbon price or green fund that reinvests verified savings.",
                  "Tamper-evident (hash-chained) logs for auditable carbon records.",
                  "Smart-grid features such as demand response and battery storage coordination.",
                  "A shared regional platform so that neighbouring institutions can benchmark against each other."])

    # ================= Chapter 10
    s += chapter("Conclusion")
    s += [P("This project delivered a complete, working Smart Campus Sustainability and Carbon Footprint Monitoring "
            "System that gives an institution what annual reports cannot: timely, granular and trustworthy information "
            "about its environmental impact. IoT readings flow through an authenticated ingestion layer into a "
            "standards-based carbon engine; robust anomaly detection finds wastage within hours; forecasting, "
            "benchmarking and scenario modelling turn data into decisions; and role-specific dashboards involve the "
            "whole campus community."),
          P(f"On the evaluation campus the system quantified an annualised footprint of about "
            f"{c['annualised_tco2e']:,.0f} tCO<sub>2</sub>e, detected every injected fault without false alarms, "
            f"forecast demand within {fc['mape_pct']}% error and identified a package of measures worth about "
            f"{sc['tco2e_saved']:,.0f} tCO<sub>2</sub>e per year. Because it is built entirely on free and "
            "open-source software and runs on an ordinary computer, it can begin as a low-risk pilot in two or three "
            "buildings and grow building by building, exactly as the phased roadmap of the project report "
            "recommends."),
          P("Beyond its own savings, a monitored campus demonstrates to students and to society how data-driven climate "
            "action can work in practice, and the live data strengthens the institution's educational mission.")]

    # ================= References
    s += unnumbered("References")
    refs = [
        "World Resources Institute and WBCSD, <i>The Greenhouse Gas Protocol: A Corporate Accounting and Reporting "
        "Standard</i>, Revised Edition, 2004.",
        "World Resources Institute, <i>GHG Protocol Scope 2 Guidance</i>, 2015.",
        "ISO 14064-1:2018, <i>Greenhouse gases - Part 1: Specification with guidance at the organization level for "
        "quantification and reporting of greenhouse gas emissions and removals</i>.",
        "ISO 50001:2018, <i>Energy management systems - Requirements with guidance for use</i>.",
        "Central Electricity Authority, Government of India, <i>CO<sub>2</sub> Baseline Database for the Indian Power "
        "Sector</i>, User Guide, latest version.",
        "IPCC, <i>2006 IPCC Guidelines for National Greenhouse Gas Inventories</i>, Vol. 2: Energy.",
        "IPCC, <i>Climate Change 2007: The Physical Science Basis</i> (AR4), global warming potentials.",
        "UK Department for Energy Security and Net Zero, <i>Greenhouse Gas Reporting: Conversion Factors</i>.",
        "Bureau of Energy Efficiency, <i>Star Rating Programme for Office Buildings</i>, Government of India.",
        "GRIHA Council, <i>GRIHA Rating System</i>; Indian Green Building Council, <i>IGBC Green Campus Rating</i>.",
        "AASHE, <i>STARS Technical Manual</i>, Version 2.2.",
        "United Nations, <i>Transforming our World: The 2030 Agenda for Sustainable Development</i>, 2015.",
        "P. J. Rousseeuw and C. Croux, 'Alternatives to the median absolute deviation', <i>Journal of the American "
        "Statistical Association</i>, 88(424), 1993.",
        "R. J. Hyndman and G. Athanasopoulos, <i>Forecasting: Principles and Practice</i>, 3rd ed., OTexts, 2021.",
        "Django Software Foundation, <i>Django Documentation</i>; Encode, <i>Django REST Framework Documentation</i>.",
        "Meta Open Source, <i>React Documentation</i>; Recharts and Leaflet project documentation.",
    ]
    s += [Paragraph(r, ParagraphStyle("ref", parent=body, fontSize=10, leading=12.3, leftIndent=24, firstLineIndent=-24, spaceAfter=2),
                    bulletText=None) for r in [f"[{i}]&nbsp;&nbsp;{t}" for i, t in enumerate(refs, 1)]]

    # ================= Appendices
    s += unnumbered("Appendix: Installation and Execution", need=4 * cm)
    s += [
          P("Requires Python 3.11+ and Node.js 20+ (both free). On Windows, run <font name='Cour'>setup.bat</font> once, then <font name='Cour'>start.bat</font>, which opens the app at http://localhost:5173; commands for other systems are in README.md. Demo logins: <b>admin</b> / admin123, <b>facility</b> / facility123, <b>student</b> / student123.")]
    return s


ABBR = [("API", "Application Programming Interface"), ("BEE", "Bureau of Energy Efficiency"),
        ("CEA", "Central Electricity Authority"), ("CO<sub>2</sub>e", "Carbon dioxide equivalent"),
        ("EPI", "Energy Performance Index"), ("GHG", "Greenhouse Gas"), ("HVAC", "Heating, Ventilation and Air "
                                                                                 "Conditioning"),
        ("IoT", "Internet of Things"), ("JWT", "JSON Web Token"), ("KPI", "Key Performance Indicator"),
        ("MAD", "Median Absolute Deviation"), ("MAPE", "Mean Absolute Percentage Error"),
        ("REST", "Representational State Transfer"), ("RBAC", "Role-Based Access Control"),
        ("STP", "Sewage Treatment Plant"), ("tCO<sub>2</sub>e", "Tonnes of carbon dioxide equivalent")]


class ListPlaceholder(Flowable):
    """Renders the list of figures/tables collected during the previous build pass."""

    store = {"figures": [], "tables": []}

    def __init__(self, kind):
        super().__init__()
        self.kind = kind

    def _rows(self):
        if self.kind == "abbr":
            small = ParagraphStyle("s", parent=cell, fontSize=10, leading=11.6)
            return [[Paragraph(f"<b>{a}</b>", small), Paragraph(b, small), ""] for a, b in ABBR]
        if self.kind == "toc":
            t0 = ParagraphStyle("t0", parent=cell, fontName="Times-B", fontSize=10.6, leading=12.2, spaceBefore=2)
            t1 = ParagraphStyle("t1", parent=cell, fontSize=10.2, leading=11, leftIndent=18)
            r0 = ParagraphStyle("r0", parent=t0, alignment=2)
            r1 = ParagraphStyle("r1", parent=cell, fontSize=10.2, leading=11, alignment=2)
            return [[Paragraph(text, t0 if lvl == 0 else t1), "", Paragraph(page, r0 if lvl == 0 else r1)]
                    for lvl, text, page in ListPlaceholder.store.get("toc", [])]
        small = ParagraphStyle("s", parent=cell, fontSize=10, leading=11.6)
        right = ParagraphStyle("r", parent=small, alignment=2)
        return [[Paragraph(n, small), Paragraph(t, small), Paragraph(PAGES.get(n, ""), right)]
                for n, t in ListPlaceholder.store[self.kind]]

    def wrap(self, aw, ah):
        rows = self._rows() or [["", "", ""]]
        widths = [aw - 1.4 * cm, 0.2 * cm, 1.2 * cm] if self.kind == "toc" else [2.4 * cm, aw - 3.6 * cm, 1.2 * cm]
        self._t = Table(rows, colWidths=widths)
        self._t.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0.3), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.3), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return self._t.wrap(aw, ah)

    def split(self, aw, ah):
        self.wrap(aw, ah)
        return self._t.split(aw, ah)

    def draw(self):
        self._t.drawOn(self.canv, 0, 0)


def build(original, out):
    body_pdf = HERE / "_body.pdf"
    # pass 1 collects figure/table numbering; pass 2 renders the lists with it
    for _ in range(3):
        figures.clear()
        tables.clear()
        TOC_ENTRIES.clear()
        chapter_no[0] = 0
        ReportDoc(body_pdf).build(story())
        ListPlaceholder.store = {"figures": list(figures), "tables": list(tables), "toc": list(TOC_ENTRIES)}
    print("built body")

    writer = PdfWriter()
    cover = PdfReader(str(original))
    for i in range(2):  # original cover page and bonafide certificate, unchanged
        writer.add_page(cover.pages[i])
    for page in PdfReader(str(body_pdf)).pages:
        writer.add_page(page)
    writer.add_metadata({"/Title": TITLE, "/Author": "Yajat M Rawal, S Surendar, Surya Swaminathan, Shivraj Singh",
                         "/Subject": "21CSC203P Advanced Programming Practice - Project Report"})
    with open(out, "wb") as fh:
        writer.write(fh)
    body_pdf.unlink()
    print("pages:", len(writer.pages))


if __name__ == "__main__":
    build(Path(sys.argv[1]), HERE / "Smart_Campus_Sustainability_Project_Report.pdf")
