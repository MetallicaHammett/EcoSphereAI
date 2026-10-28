# EcoSphere AI – Smart Campus Sustainability & Carbon Footprint Monitoring System

A working implementation of the project report *"Smart Campus Sustainability and Carbon Footprint
Monitoring System"* (21CSC203P, SRM IST Vadapalani). It measures electricity, water, waste, transport
and green cover, converts activity data into GHG Protocol emissions, detects waste and faults
automatically, forecasts demand, models interventions and reports against targets.

**Everything is free and open source** – Python, Django, Django REST Framework, SQLite, NumPy,
ReportLab, React, Vite, Recharts and Leaflet with OpenStreetMap tiles. No paid APIs, cloud accounts
or licence keys are needed. It runs entirely on your own computer.

## Quick start (Windows)

Prerequisites (free): [Python 3.11+](https://www.python.org/downloads/) and [Node.js 20+](https://nodejs.org/).

1. Double-click **`setup.bat`** once. It creates the virtual environment, installs dependencies,
   builds the database and generates 120 days of realistic campus data.
2. Double-click **`start.bat`**. It opens the API, the live IoT simulator and the web app, then
   opens <http://localhost:5173> in your browser.

Demo accounts (test data created by `seed_demo`):

| Username   | Password      | Role                                              |
|------------|---------------|---------------------------------------------------|
| `admin`    | `admin123`    | Administrator / sustainability officer – everything |
| `facility` | `facility123` | Facility team – alerts, fuel and waste logs        |
| `student`  | `student123`  | Student / staff – dashboards and community portal  |

New students can also register from the sign-in page. The Django admin is at <http://127.0.0.1:8010/admin/>.

### Manual commands (any OS)

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt        # Windows: .venv\Scripts\pip
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py seed_demo --reset           # demo campus + 120 days of history
../.venv/bin/python manage.py runserver 8010              # API on :8010
../.venv/bin/python manage.py simulate                    # (2nd terminal) live IoT readings
cd ../frontend && npm install && npm run dev              # (3rd terminal) web app on :5173
```

Run the backend tests with `python manage.py test` inside `backend/` (18 end-to-end tests).

> The demo history is generated relative to *today*. If you come back days later, run
> `python manage.py seed_demo --reset` to refresh it (this wipes campus data, not user accounts).

## What the system does (mapped to the report)

| Report section | Where it lives |
|---|---|
| 3. Carbon footprint framework – *Emissions = activity × factor*, Scope 1/2/3, location- and market-based Scope 2 | `backend/analytics/services/carbon.py` |
| 3.1 Configurable, version-controlled emission factors (CEA grid factor etc.) | Settings & data → Emission factors |
| 3.2 Boundary and baseline | Settings & data → Campus & targets |
| 4.1 Sensing layer – meters, water, indoor environment, solar, weather | `backend/analytics/simulation.py`, `simulate` command |
| 4.2 Connectivity – gateways forward readings with device authentication | `POST /api/ingest/` with `X-Gateway-Key` |
| 4.3 Data platform – validation, quality flags (never silently corrected), aggregation | `monitoring/views.py`, Data quality tab |
| 4.4 Anomaly detection – after-hours load, spikes, night-flow leaks, stuck/offline meters, CO₂ | `analytics/services/anomaly.py` |
| 4.4 Forecasting – trend + weekday + holiday + temperature regression | `analytics/services/forecast.py` |
| 4.4 Benchmarking (kWh/m², L/person) and scenario modelling (LED, solar, set-points, controls, e-buses) | Forecast & scenarios page |
| 4.5 Management dashboard, operations console with work orders, community portal, reporting | React pages in `frontend/src/pages/` |
| 5.1–5.6 Energy, water, waste, transport, green cover, engagement modules | One page each |
| 9. KPIs (tCO₂e/student, tCO₂e/m², kWh/m², renewable share, L/person/day, diversion rate, mode share…) | Dashboard and module pages |
| Reporting – GHG inventory PDF and CSV exports | Reports page, `analytics/services/reports.py` |

### Injected demo faults

`seed_demo` deliberately plants faults so the detector has something real to find: air-conditioning
left on overnight in Academic Block B, a leaking tank valve in Boys Hostel 1, a lab test rig left on
in Tech Park Labs, a poorly ventilated library hall and one impossible meter value. Run
`python manage.py simulate --inject leak` (or `ac`, `spike`) to stream a live fault.

## Architecture

```
ESP32 / gateways / simulator ──POST /api/ingest/──►  Django REST API  ◄──JWT──  React SPA (Vite)
                                                        │
                       SQLite (readings, factors, logs) ┤  services: carbon · anomaly · forecast
                                                        │           scenarios · insights · reports
```

* `backend/accounts` – custom user with roles, JWT login/registration, role-based permissions.
* `backend/monitoring` – buildings, gateways, meters, readings, indoor/weather data, calendar, alerts.
* `backend/sustainability` – emission factors, fuel/refrigerant logs, waste, commute surveys, trees, targets.
* `backend/analytics` – the carbon engine and analytics services, REST views, `seed_demo` and `simulate`.
* `frontend/src` – React + TypeScript app (React Query, Zustand, Recharts, Leaflet).

### Connecting a real device

Any device that can make an HTTP request can report readings – for example an ESP32 reading a Modbus
energy meter. Each reading's `value` is the consumption during the interval:

```bash
curl -X POST http://127.0.0.1:8010/api/ingest/ -H "Content-Type: application/json" \
  -H "X-Gateway-Key: <key from Settings & data → Meters & gateways>" \
  -d "{\"readings\":[{\"serial\":\"EM-ACA\",\"value\":42.5,\"interval_minutes\":15}]}"
```

## Notes on the numbers

Emission factors shipped with the demo are indicative defaults (CEA grid factor ≈ 0.716 kg/kWh,
IPCC/DEFRA fuel, waste and transport factors). As the report says, confirm the latest official CEA
value before external disclosure and publish it as a new factor version – earlier results are kept
unchanged. Tree sequestration is reported separately and never netted against emissions.
