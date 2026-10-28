from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole, ReadOnlyOrAdmin, ReadOnlyOrOperator

from .models import Alert, Building, CalendarDay, CampusSettings, Gateway, Meter, Reading
from .serializers import (AlertSerializer, BuildingSerializer, CalendarDaySerializer, CampusSettingsSerializer,
                          GatewaySerializer, MeterSerializer)


class RecentListMixin:
    """Caps list responses so tables stay fast; ``?limit=`` raises the cap up to 2000."""

    default_limit = 300

    def list(self, request, *args, **kwargs):
        try:
            limit = min(max(int(request.query_params.get("limit", self.default_limit)), 1), 2000)
        except ValueError:
            limit = self.default_limit
        queryset = self.filter_queryset(self.get_queryset())[:limit]
        return Response(self.get_serializer(queryset, many=True).data)


class CampusSettingsView(APIView):
    permission_classes = [ReadOnlyOrAdmin]

    def get(self, request):
        return Response(CampusSettingsSerializer(CampusSettings.load()).data)

    def put(self, request):
        serializer = CampusSettingsSerializer(CampusSettings.load(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class BuildingViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrAdmin]
    serializer_class = BuildingSerializer
    queryset = Building.objects.all()


class GatewayViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = GatewaySerializer
    queryset = Gateway.objects.order_by("name")


class MeterViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrAdmin]
    serializer_class = MeterSerializer

    def get_queryset(self):
        qs = Meter.objects.select_related("building")
        if kind := self.request.query_params.get("kind"):
            qs = qs.filter(kind=kind)
        if building := self.request.query_params.get("building"):
            qs = qs.filter(building_id=building)
        return qs


class CalendarDayViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrAdmin]
    serializer_class = CalendarDaySerializer
    queryset = CalendarDay.objects.all()


class AlertViewSet(RecentListMixin, viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrOperator]
    serializer_class = AlertSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        qs = Alert.objects.select_related("building", "meter", "assigned_to")
        params = self.request.query_params
        for field in ("status", "category", "severity", "building"):
            if value := params.get(field):
                qs = qs.filter(**{field: value})
        return qs


class IngestView(APIView):
    """
    Device ingestion endpoint used by edge gateways (or ESP32 boards).

    Header ``X-Gateway-Key: <key>`` and body
    ``{"readings": [{"serial": "EM-ACA-01", "value": 12.4, "interval_minutes": 15,
    "timestamp": "2026-10-25T10:15:00+05:30"}]}`` where ``value`` is the consumption during the interval
    starting at ``timestamp`` (defaults: now, 15 minutes).
    Out-of-range values are stored but flagged as suspect rather than silently corrected.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ingest"

    def post(self, request):
        key = request.headers.get("X-Gateway-Key", "")
        gateway = Gateway.objects.filter(key=key, is_active=True).first() if key else None
        if gateway is None:
            return Response({"detail": "Unknown or inactive gateway key."}, status=status.HTTP_401_UNAUTHORIZED)

        items = request.data.get("readings") if isinstance(request.data, dict) else request.data
        if not isinstance(items, list) or not items:
            return Response({"detail": "Body must contain a non-empty 'readings' list."},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(items) > 5000:
            return Response({"detail": "At most 5000 readings per request."}, status=status.HTTP_400_BAD_REQUEST)

        serials = {str(i.get("serial")) for i in items if isinstance(i, dict)}
        meters = {m.serial: m for m in Meter.objects.filter(serial__in=serials, is_active=True)}
        now = timezone.now()
        rows, rejected = [], []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                rejected.append({"index": index, "error": "Reading must be an object."})
                continue
            meter = meters.get(str(item.get("serial")))
            if meter is None:
                rejected.append({"index": index, "error": f"Unknown or inactive meter '{item.get('serial')}'."})
                continue
            try:
                value = float(item.get("value"))
            except (TypeError, ValueError):
                rejected.append({"index": index, "error": "Value must be numeric."})
                continue
            if value != value or value in (float("inf"), float("-inf")):
                rejected.append({"index": index, "error": "Value must be finite."})
                continue
            ts = now
            if item.get("timestamp"):
                ts = parse_datetime(str(item["timestamp"]))
                if ts is None:
                    rejected.append({"index": index, "error": "Timestamp must be ISO 8601."})
                    continue
                if timezone.is_naive(ts):
                    ts = timezone.make_aware(ts)
                if ts > now + timezone.timedelta(minutes=10):
                    rejected.append({"index": index, "error": "Timestamp is in the future."})
                    continue
            try:
                interval = int(item.get("interval_minutes", 15))
            except (TypeError, ValueError):
                interval = 0
            if not 1 <= interval <= 1440:
                rejected.append({"index": index, "error": "interval_minutes must be between 1 and 1440."})
                continue
            quality = Reading.Quality.OK
            # max_value is defined per hour, so scale it to the reading's interval.
            if value < 0 or (meter.max_value and value > meter.max_value * interval / 60):
                quality = Reading.Quality.SUSPECT
            rows.append(Reading(meter=meter, timestamp=ts, value=value, interval_minutes=interval, quality=quality))

        Reading.objects.bulk_create(rows)
        latest = {}
        for row in rows:
            if row.meter_id not in latest or row.timestamp > latest[row.meter_id]:
                latest[row.meter_id] = row.timestamp
        for meter_id, ts in latest.items():
            Meter.objects.filter(pk=meter_id).exclude(last_reading_at__gte=ts).update(last_reading_at=ts)
        gateway.last_seen = now
        gateway.save(update_fields=["last_seen"])
        return Response({"accepted": len(rows), "rejected": rejected},
                        status=status.HTTP_201_CREATED if rows else status.HTTP_400_BAD_REQUEST)
