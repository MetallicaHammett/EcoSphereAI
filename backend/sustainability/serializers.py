from django.db.models import Max
from rest_framework import serializers

from .models import CommuteSurvey, EmissionFactor, FuelLog, ReductionTarget, Tree, WasteLog


class EmissionFactorSerializer(serializers.ModelSerializer):
    activity_label = serializers.CharField(source="get_activity_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True, default=None)

    class Meta:
        model = EmissionFactor
        fields = ["id", "activity", "activity_label", "scope", "value", "activity_unit", "source", "valid_from",
                  "version", "notes", "created_at", "created_by_name"]
        read_only_fields = ["version", "created_at"]

    def validate_value(self, value):
        if value < 0:
            raise serializers.ValidationError("Emission factor cannot be negative.")
        return value

    def create(self, validated_data):
        latest = EmissionFactor.objects.filter(activity=validated_data["activity"]).aggregate(v=Max("version"))["v"]
        validated_data["version"] = (latest or 0) + 1
        return super().create(validated_data)


class FuelLogSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    activity_label = serializers.CharField(source="get_activity_display", read_only=True)
    building_name = serializers.CharField(source="building.name", read_only=True, default=None)

    class Meta:
        model = FuelLog
        fields = ["id", "date", "category", "category_label", "activity", "activity_label", "quantity", "asset",
                  "distance_km", "building", "building_name", "notes"]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be positive.")
        return value


class WasteLogSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    disposal_label = serializers.CharField(source="get_disposal_display", read_only=True)
    building_name = serializers.CharField(source="building.name", read_only=True, default=None)

    class Meta:
        model = WasteLog
        fields = ["id", "date", "building", "building_name", "category", "category_label", "disposal",
                  "disposal_label", "weight_kg", "notes"]

    def validate_weight_kg(self, value):
        if value <= 0:
            raise serializers.ValidationError("Weight must be positive.")
        return value


class CommuteSurveySerializer(serializers.ModelSerializer):
    mode_label = serializers.CharField(source="get_mode_display", read_only=True)

    class Meta:
        model = CommuteSurvey
        fields = ["id", "respondent", "mode", "mode_label", "distance_km", "days_per_week", "created_at"]
        read_only_fields = ["created_at"]

    def validate_distance_km(self, value):
        if not 0 <= value <= 200:
            raise serializers.ValidationError("Distance must be between 0 and 200 km.")
        return value

    def validate_days_per_week(self, value):
        if not 1 <= value <= 7:
            raise serializers.ValidationError("Days per week must be between 1 and 7.")
        return value


class TreeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tree
        fields = ["id", "species", "zone", "count", "planted_year", "sequestration_kg_per_tree",
                  "canopy_m2_per_tree"]


class ReductionTargetSerializer(serializers.ModelSerializer):
    target_tco2e = serializers.FloatField(read_only=True)

    class Meta:
        model = ReductionTarget
        fields = ["id", "name", "baseline_year", "baseline_tco2e", "target_year", "reduction_pct", "target_tco2e"]

    def validate(self, attrs):
        baseline = attrs.get("baseline_year", getattr(self.instance, "baseline_year", None))
        target = attrs.get("target_year", getattr(self.instance, "target_year", None))
        if baseline and target and target <= baseline:
            raise serializers.ValidationError("Target year must be after the baseline year.")
        pct = attrs.get("reduction_pct")
        if pct is not None and not 0 < pct <= 100:
            raise serializers.ValidationError("Reduction must be between 0 and 100%.")
        return attrs
