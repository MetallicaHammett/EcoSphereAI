from datetime import timedelta

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsOperator
from monitoring.models import Building

from .services import anomaly, forecast, insights, reports, scenarios
from .services.common import RangeError, parse_range


class RangeView(APIView):
    default_days = 30

    def get(self, request):
        try:
            rng = parse_range(request.query_params, self.default_days)
        except RangeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self.respond(request, rng)


def _building(request):
    value = request.query_params.get("building")
    if not value:
        return None
    try:
        return Building.objects.get(pk=int(value)).pk
    except (ValueError, Building.DoesNotExist):
        return -1


class OverviewView(RangeView):
    def respond(self, request, rng):
        return Response(insights.overview(rng))


class EnergyView(RangeView):
    def respond(self, request, rng):
        building = _building(request)
        if building == -1:
            return Response({"detail": "Unknown building."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(insights.energy(rng, building, request.query_params.get("granularity", "day")))


class WaterView(RangeView):
    def respond(self, request, rng):
        return Response(insights.water(rng))


class WasteView(RangeView):
    default_days = 90

    def respond(self, request, rng):
        return Response(insights.waste(rng))


class TransportView(RangeView):
    def respond(self, request, rng):
        return Response(insights.transport(rng))


class BenchmarkView(RangeView):
    def respond(self, request, rng):
        return Response(insights.benchmark(rng))


class LiveView(APIView):
    def get(self, request):
        return Response(insights.live())


class GreenView(APIView):
    def get(self, request):
        return Response(insights.green())


class LeaderboardView(APIView):
    def get(self, request):
        return Response(insights.leaderboard())


class DataQualityView(APIView):
    def get(self, request):
        return Response(insights.data_quality())


class ForecastView(APIView):
    def get(self, request):
        try:
            days = min(max(int(request.query_params.get("days", 30)), 1), 90)
        except ValueError:
            return Response({"detail": "days must be a whole number."}, status=status.HTTP_400_BAD_REQUEST)
        building = _building(request)
        if building == -1:
            return Response({"detail": "Unknown building."}, status=status.HTTP_400_BAD_REQUEST)
        result = forecast.forecast(days, building)
        if "error" in result:
            return Response({"detail": result["error"]}, status=status.HTTP_409_CONFLICT)
        return Response(result)


class ScenarioView(APIView):
    def get(self, request):
        return Response(scenarios.run({}))

    def post(self, request):
        return Response(scenarios.run(request.data if isinstance(request.data, dict) else {}))


class AnomalyScanView(APIView):
    permission_classes = [IsOperator]

    def post(self, request):
        return Response(anomaly.scan())


class GhgReportView(RangeView):
    default_days = 365

    def respond(self, request, rng):
        response = HttpResponse(reports.ghg_pdf(rng), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="ghg-inventory-{rng.start}-to-{rng.end - timedelta(days=1)}.pdf"'
        return response


class CsvExportView(RangeView):
    default_days = 90

    def respond(self, request, rng):
        dataset = request.query_params.get("dataset", "emissions")
        content = reports.export_csv(dataset, rng)
        if content is None:
            return Response({"detail": f"dataset must be one of {', '.join(reports.CSV_DATASETS)}."},
                            status=status.HTTP_400_BAD_REQUEST)
        response = HttpResponse(content, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{dataset}-{rng.start}-to-{rng.end - timedelta(days=1)}.csv"'
        return response


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "ok"})
