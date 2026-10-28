from datetime import timedelta

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import ReadOnlyOrAdmin, ReadOnlyOrOperator
from analytics.services.carbon import commute_footprint
from monitoring.views import RecentListMixin

from .models import CommuteSurvey, EmissionFactor, FuelLog, ReductionTarget, Tree, WasteLog
from .serializers import (CommuteSurveySerializer, EmissionFactorSerializer, FuelLogSerializer,
                          ReductionTargetSerializer, TreeSerializer, WasteLogSerializer)


class DaysFilterMixin:
    date_field = "date"

    def filter_days(self, qs):
        try:
            days = int(self.request.query_params.get("days", 0))
        except ValueError:
            days = 0
        if days > 0:
            since = timezone.localdate() - timedelta(days=days)
            qs = qs.filter(**{f"{self.date_field}__gt": since})
        return qs


class EmissionFactorViewSet(viewsets.ModelViewSet):
    """Factors are append-only in practice: publish a new version instead of editing history."""

    permission_classes = [ReadOnlyOrAdmin]
    serializer_class = EmissionFactorSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        qs = EmissionFactor.objects.select_related("created_by")
        if activity := self.request.query_params.get("activity"):
            qs = qs.filter(activity=activity)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class FuelLogViewSet(DaysFilterMixin, RecentListMixin, viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrOperator]
    serializer_class = FuelLogSerializer

    def get_queryset(self):
        qs = self.filter_days(FuelLog.objects.select_related("building"))
        if category := self.request.query_params.get("category"):
            qs = qs.filter(category=category)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class WasteLogViewSet(DaysFilterMixin, RecentListMixin, viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrOperator]
    serializer_class = WasteLogSerializer

    def get_queryset(self):
        return self.filter_days(WasteLog.objects.select_related("building"))

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CommuteSurveyViewSet(RecentListMixin, viewsets.ModelViewSet):
    """Everyone can submit their commute; individuals only see their own answers (privacy)."""

    permission_classes = [IsAuthenticated]
    serializer_class = CommuteSurveySerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return CommuteSurvey.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        response.data["footprint"] = commute_footprint(
            response.data["mode"], response.data["distance_km"], response.data["days_per_week"])
        return response


class TreeViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrOperator]
    serializer_class = TreeSerializer
    queryset = Tree.objects.all()


class ReductionTargetViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadOnlyOrAdmin]
    serializer_class = ReductionTargetSerializer
    queryset = ReductionTarget.objects.all()
