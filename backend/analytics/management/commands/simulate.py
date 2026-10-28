"""
Live IoT simulator. Acts like an edge gateway: every interval it reads the (simulated) meters
and POSTs them to the REST ingestion endpoint with its gateway key, exactly as an ESP32 or
LoRaWAN gateway would. Indoor-environment and weather values are written alongside.

    python manage.py simulate                     # posts to http://127.0.0.1:8010/api/ingest/
    python manage.py simulate --interval 30 --inject ac
    python manage.py simulate --direct            # no web server needed, writes to the DB
"""

import json
import random
import time
import urllib.error
import urllib.request
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from analytics import simulation as sim
from analytics.services import anomaly
from analytics.services.common import non_working_days
from monitoring.models import Building, EnvReading, Gateway, Meter, Reading, WeatherReading


class Command(BaseCommand):
    help = "Stream simulated live meter readings into the platform."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=60,
                            help="Seconds between readings, rounded to whole minutes (default 60)")
        parser.add_argument("--url", default="http://127.0.0.1:8010/api/ingest/")
        parser.add_argument("--direct", action="store_true", help="Write to the database instead of HTTP")
        parser.add_argument("--inject", choices=["ac", "leak", "spike"], help="Inject a live fault for demos")
        parser.add_argument("--scan-every", type=int, default=15, help="Run anomaly scan every N minutes")
        parser.add_argument("--once", action="store_true", help="Send a single batch and exit")

    def handle(self, *args, **opts):
        interval = max(60, round(opts["interval"] / 60) * 60)  # readings carry whole-minute intervals
        gateway = Gateway.objects.filter(is_active=True).first()
        if gateway is None or not Building.objects.exists():
            raise CommandError("No campus data. Run 'python manage.py seed_demo' first.")
        meters = {m.serial: m for m in Meter.objects.filter(is_active=True)}
        buildings = {b.code: b for b in Building.objects.all()}
        rnd = random.Random()
        last_scan = timezone.now()
        self.stdout.write(self.style.SUCCESS(
            f"Streaming every {interval}s via {'database' if opts['direct'] else opts['url']} "
            f"(Ctrl+C to stop)."))
        try:
            while True:
                now = timezone.localtime()
                batch = self._batch(now, interval, meters, buildings, rnd, opts["inject"])
                if opts["direct"]:
                    self._write_direct(batch, meters, now, interval)
                    status = f"stored {len(batch)}"
                else:
                    status = self._post(opts["url"], gateway.key, batch)
                self.stdout.write(f"[{now:%H:%M:%S}] {status} readings")
                if timezone.now() - last_scan >= timedelta(minutes=opts["scan_every"]):
                    result = anomaly.scan()
                    last_scan = timezone.now()
                    if result["created"]:
                        self.stdout.write(self.style.WARNING(f"  {result['created']} new alert(s): "
                                                             + "; ".join(result["titles"])))
                if opts["once"]:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write("Stopped.")

    def _batch(self, now, interval, meters, buildings, rnd, inject):
        working = now.date() not in non_working_days(now.date(), now.date() + timedelta(days=1))
        w = sim.weather(now)
        minutes = interval // 60
        frac = minutes / 60  # hours covered by each reading
        ts = (now - timedelta(minutes=minutes)).isoformat()
        batch, total_water = [], 0.0
        WeatherReading.objects.create(timestamp=now, temperature=w.temperature, humidity=w.humidity,
                                      irradiance=w.irradiance, rainfall_mm=w.rainfall_mm * frac)
        for code, name, btype, area, occ, _lat, _lng, kwp, has_env in sim.BUILDINGS:
            if code not in buildings:
                continue
            load = sim.building_load_kw(btype, area, now, working, w.temperature, rnd.uniform(0.95, 1.05))
            if inject == "ac" and code == "ACB":
                load += 160
            if inject == "spike" and code == "TPL":
                load += 300
            gen = sim.solar_kw(kwp, w.irradiance, rnd.uniform(0.92, 1.04)) if kwp else 0.0
            water = sim.water_klph(btype, occ, now.hour, working, rnd.uniform(0.85, 1.15))
            if inject == "leak" and code == "BH1":
                water += 2.4
            total_water += water
            entries = [(f"EM-{code}", max(load - gen, 0)), (f"WM-{code}", water)]
            if kwp:
                entries.append((f"SM-{code}", gen))
            for serial, rate in entries:
                if serial in meters:
                    batch.append({"serial": serial, "value": round(rate * frac, 4),
                                  "interval_minutes": minutes, "timestamp": ts})
            if has_env:
                t, h, co2, people = sim.indoor(btype, occ, now, working, w.temperature, rnd)
                EnvReading.objects.create(building=buildings[code], timestamp=now, temperature=t, humidity=h,
                                          co2_ppm=co2, occupancy=people)
        for source, share in sim.SOURCE_SHARES.items():
            serial = f"WS-{source.upper()}"
            if serial in meters:
                batch.append({"serial": serial, "value": round(total_water * 1.04 * share * frac, 4),
                              "interval_minutes": minutes, "timestamp": ts})
        return batch

    def _post(self, url, key, batch):
        request = urllib.request.Request(url, data=json.dumps({"readings": batch}).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "X-Gateway-Key": key})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.loads(response.read())
                return f"accepted {body.get('accepted')}/{len(batch)}"
        except urllib.error.HTTPError as exc:
            return f"server rejected batch ({exc.code}: {exc.read()[:200]!r}) -"
        except urllib.error.URLError as exc:
            return f"server unreachable ({exc.reason}); is 'python manage.py runserver' running? 0"

    def _write_direct(self, batch, meters, now, interval):
        rows = [Reading(meter=meters[b["serial"]], timestamp=now - timedelta(minutes=interval // 60), value=b["value"],
                        interval_minutes=b["interval_minutes"]) for b in batch]
        Reading.objects.bulk_create(rows)
        Meter.objects.filter(serial__in=[b["serial"] for b in batch]).update(last_reading_at=now)
        Gateway.objects.filter(is_active=True).update(last_seen=now)
