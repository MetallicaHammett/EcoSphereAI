from django.utils import timezone
from rest_framework import serializers

from .models import Alert, Building, CalendarDay, CampusSettings, Gateway, Meter


class CampusSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampusSettings
        exclude = ["id"]

    def validate_green_power_share(self, value):
        if not 0 <= value <= 1:
            raise serializers.ValidationError("Must be between 0 and 1.")
        return value


class BuildingSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Building
        fields = ["id", "name", "code", "type", "type_label", "area_m2", "occupants", "latitude", "longitude"]

    def validate_area_m2(self, value):
        if value <= 0:
            raise serializers.ValidationError("Area must be positive.")
        return value


class GatewaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Gateway
        fields = ["id", "name", "key", "is_active", "last_seen"]
        read_only_fields = ["key", "last_seen"]


class MeterSerializer(serializers.ModelSerializer):
    building_name = serializers.CharField(source="building.name", read_only=True, default=None)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    online = serializers.SerializerMethodField()

    class Meta:
        model = Meter
        fields = ["id", "building", "building_name", "gateway", "name", "serial", "kind", "kind_label", "source",
                  "unit", "capacity", "max_value", "is_active", "last_reading_at", "online"]
        read_only_fields = ["last_reading_at"]

    def get_online(self, obj):
        return bool(obj.last_reading_at and timezone.now() - obj.last_reading_at < timezone.timedelta(hours=2))


class CalendarDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarDay
        fields = ["id", "date", "kind", "label"]


class AlertSerializer(serializers.ModelSerializer):
    building_name = serializers.CharField(source="building.name", read_only=True, default=None)
    meter_name = serializers.CharField(source="meter.name", read_only=True, default=None)
    assigned_to_name = serializers.CharField(source="assigned_to.username", read_only=True, default=None)

    class Meta:
        model = Alert
        fields = ["id", "building", "building_name", "meter", "meter_name", "category", "alert_type", "severity",
                  "title", "message", "status", "assigned_to", "assigned_to_name", "notes", "excess_quantity",
                  "excess_unit", "estimated_cost", "occurred_on", "created_at", "updated_at", "resolved_at"]
        read_only_fields = [f for f in fields if f not in ("status", "assigned_to", "notes", "severity")]

    def update(self, instance, validated_data):
        status = validated_data.get("status")
        if status == Alert.Status.RESOLVED and instance.status != Alert.Status.RESOLVED:
            instance.resolved_at = timezone.now()
        elif status and status != Alert.Status.RESOLVED:
            instance.resolved_at = None
        return super().update(instance, validated_data)
