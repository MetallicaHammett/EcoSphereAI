from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.views import MeView, RegisterView, UserViewSet
from analytics import views as analytics
from monitoring.views import (AlertViewSet, BuildingViewSet, CalendarDayViewSet, CampusSettingsView, GatewayViewSet,
                              IngestView, MeterViewSet)
from sustainability.views import (CommuteSurveyViewSet, EmissionFactorViewSet, FuelLogViewSet,
                                  ReductionTargetViewSet, TreeViewSet, WasteLogViewSet)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("buildings", BuildingViewSet, basename="building")
router.register("meters", MeterViewSet, basename="meter")
router.register("gateways", GatewayViewSet, basename="gateway")
router.register("calendar", CalendarDayViewSet, basename="calendar")
router.register("alerts", AlertViewSet, basename="alert")
router.register("factors", EmissionFactorViewSet, basename="factor")
router.register("fuel-logs", FuelLogViewSet, basename="fuel-log")
router.register("waste-logs", WasteLogViewSet, basename="waste-log")
router.register("commute", CommuteSurveyViewSet, basename="commute")
router.register("trees", TreeViewSet, basename="tree")
router.register("targets", ReductionTargetViewSet, basename="target")

api = [
    path("auth/login/", TokenObtainPairView.as_view()),
    path("auth/refresh/", TokenRefreshView.as_view()),
    path("auth/register/", RegisterView.as_view()),
    path("auth/me/", MeView.as_view()),
    path("settings/", CampusSettingsView.as_view()),
    path("ingest/", IngestView.as_view()),
    path("health/", analytics.HealthView.as_view()),
    path("analytics/overview/", analytics.OverviewView.as_view()),
    path("analytics/energy/", analytics.EnergyView.as_view()),
    path("analytics/water/", analytics.WaterView.as_view()),
    path("analytics/waste/", analytics.WasteView.as_view()),
    path("analytics/transport/", analytics.TransportView.as_view()),
    path("analytics/green/", analytics.GreenView.as_view()),
    path("analytics/live/", analytics.LiveView.as_view()),
    path("analytics/benchmark/", analytics.BenchmarkView.as_view()),
    path("analytics/leaderboard/", analytics.LeaderboardView.as_view()),
    path("analytics/data-quality/", analytics.DataQualityView.as_view()),
    path("analytics/forecast/", analytics.ForecastView.as_view()),
    path("analytics/scenarios/", analytics.ScenarioView.as_view()),
    path("analytics/anomalies/scan/", analytics.AnomalyScanView.as_view()),
    path("reports/ghg.pdf", analytics.GhgReportView.as_view()),
    path("reports/export.csv", analytics.CsvExportView.as_view()),
    path("", include(router.urls)),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api)),
]
