"""
End-to-end tests: seed a short demo campus, then exercise the carbon engine, anomaly
detector, ingestion API, permissions and every analytics endpoint.

    python manage.py test
"""

import io
from datetime import date, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from analytics.services.carbon import FactorBook, emission_items
from analytics.services.common import DateRange
from monitoring.models import Alert, Gateway, Reading
from sustainability.models import EmissionFactor


class CampusTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", days=45, stdout=io.StringIO())

    def client_for(self, username):
        client = APIClient()
        client.force_authenticate(User.objects.get(username=username))
        return client


class CarbonEngineTests(CampusTestCase):
    def test_emissions_equal_activity_times_factor(self):
        today = timezone.localdate()
        rng = DateRange(today - timedelta(days=7), today)
        items = [i for i in emission_items(rng) if i.activity == "electricity_grid"]
        self.assertTrue(items)
        for item in items:
            self.assertAlmostEqual(item.kg, item.quantity * 0.716, places=6)
            self.assertEqual(item.scope, 2)

    def test_new_factor_version_only_applies_from_its_date(self):
        today = timezone.localdate()
        EmissionFactor.objects.create(activity="electricity_grid", scope=2, value=0.5, activity_unit="kWh",
                                      source="test", valid_from=today - timedelta(days=2), version=3)
        book = FactorBook()
        self.assertEqual(book.value("electricity_grid", today), 0.5)
        self.assertEqual(book.value("electricity_grid", today - timedelta(days=5)), 0.716)
        self.assertEqual(book.value("electricity_grid", date(2024, 1, 1)), 0.757)

    def test_suspect_readings_are_not_counted(self):
        today = timezone.localdate()
        rng = DateRange(today - timedelta(days=3), today + timedelta(days=1))
        total = sum(i.quantity for i in emission_items(rng) if i.activity == "electricity_grid")
        self.assertLess(total, 99999)  # the injected 99,999 kWh spike is excluded

    def test_all_three_scopes_present(self):
        today = timezone.localdate()
        scopes = {i.scope for i in emission_items(DateRange(today - timedelta(days=30), today))}
        self.assertEqual(scopes, {1, 2, 3})


class AnomalyTests(CampusTestCase):
    def test_injected_faults_are_detected(self):
        types = set(Alert.objects.values_list("alert_type", flat=True))
        self.assertTrue({"after_hours", "spike", "leak", "co2_high", "impossible_value"} <= types)
        self.assertTrue(Alert.objects.filter(alert_type="after_hours", building__code="ACB").exists())
        self.assertTrue(Alert.objects.filter(alert_type="leak", building__code="BH1").exists())

    def test_scan_is_idempotent(self):
        before = Alert.objects.count()
        response = self.client_for("facility").post("/api/analytics/anomalies/scan/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Alert.objects.count(), before)


class IngestTests(CampusTestCase):
    def test_gateway_ingest_validates_and_flags(self):
        key = Gateway.objects.first().key
        client = APIClient()
        body = {"readings": [
            {"serial": "EM-ACA", "value": 10, "interval_minutes": 15},
            {"serial": "EM-ACA", "value": 50000, "interval_minutes": 15},
            {"serial": "missing", "value": 1},
            {"serial": "EM-ACA", "value": "abc"},
        ]}
        response = client.post("/api/ingest/", body, format="json", HTTP_X_GATEWAY_KEY=key)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["accepted"], 2)
        self.assertEqual(len(response.data["rejected"]), 2)
        self.assertTrue(Reading.objects.filter(value=50000, quality=Reading.Quality.SUSPECT).exists())

    def test_bad_key_rejected(self):
        response = APIClient().post("/api/ingest/", {"readings": [{"serial": "EM-ACA", "value": 1}]},
                                    format="json", HTTP_X_GATEWAY_KEY="wrong")
        self.assertEqual(response.status_code, 401)


class PermissionTests(CampusTestCase):
    def test_login_and_me(self):
        client = APIClient()
        token = client.post("/api/auth/login/", {"username": "student", "password": "student123"}, format="json")
        self.assertEqual(token.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
        self.assertEqual(client.get("/api/auth/me/").data["role"], "community")

    def test_anonymous_blocked(self):
        self.assertEqual(APIClient().get("/api/analytics/overview/").status_code, 401)

    def test_student_cannot_change_data(self):
        student = self.client_for("student")
        self.assertEqual(student.post("/api/factors/", {}).status_code, 403)
        self.assertEqual(student.post("/api/waste-logs/", {}).status_code, 403)
        self.assertEqual(student.patch(f"/api/alerts/{Alert.objects.first().id}/", {"status": "resolved"}).status_code, 403)
        self.assertEqual(student.get("/api/users/").status_code, 403)

    def test_facility_resolves_alert(self):
        alert = Alert.objects.first()
        response = self.client_for("facility").patch(f"/api/alerts/{alert.id}/", {"status": "resolved", "notes": "Fixed"})
        self.assertEqual(response.status_code, 200)
        alert.refresh_from_db()
        self.assertIsNotNone(alert.resolved_at)

    def test_admin_cannot_demote_self(self):
        admin = User.objects.get(username="admin")
        response = self.client_for("admin").patch(f"/api/users/{admin.id}/", {"role": "community"})
        self.assertEqual(response.status_code, 400)

    def test_commute_answers_are_private(self):
        student = self.client_for("student")
        response = student.post("/api/commute/", {"mode": "car", "distance_km": 10, "days_per_week": 5})
        self.assertEqual(response.status_code, 201)
        self.assertGreater(response.data["footprint"]["annual_kg"], 0)
        self.assertEqual(len(student.get("/api/commute/").data), 1)  # not the 400 seeded responses


class EndpointTests(CampusTestCase):
    def test_every_analytics_endpoint(self):
        client = self.client_for("admin")
        for url in ["/api/analytics/overview/?days=30", "/api/analytics/overview/?period=ytd",
                    "/api/analytics/energy/?days=7&granularity=hour", "/api/analytics/energy/?days=30&building=1",
                    "/api/analytics/water/", "/api/analytics/waste/", "/api/analytics/transport/",
                    "/api/analytics/green/", "/api/analytics/live/", "/api/analytics/benchmark/",
                    "/api/analytics/leaderboard/", "/api/analytics/data-quality/", "/api/analytics/forecast/?days=30",
                    "/api/analytics/scenarios/", "/api/reports/ghg.pdf?days=30",
                    "/api/reports/export.csv?dataset=emissions&days=7"]:
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 200)

    def test_invalid_ranges(self):
        client = self.client_for("admin")
        self.assertEqual(client.get("/api/analytics/overview/?days=abc").status_code, 400)
        self.assertEqual(client.get("/api/analytics/overview/?start=2026-02-01&end=2026-01-01").status_code, 400)
        self.assertEqual(client.get("/api/reports/export.csv?dataset=nope").status_code, 400)

    def test_forecast_is_reasonable(self):
        data = self.client_for("admin").get("/api/analytics/forecast/?days=14").data
        self.assertEqual(len(data["forecast"]), 14)
        self.assertLess(data["model"]["mape_pct"], 10)

    def test_pdf_is_a_pdf(self):
        response = self.client_for("admin").get("/api/reports/ghg.pdf?days=30")
        self.assertTrue(response.content.startswith(b"%PDF"))
