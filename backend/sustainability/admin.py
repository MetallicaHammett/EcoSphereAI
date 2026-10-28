from django.contrib import admin

from .models import CommuteSurvey, EmissionFactor, FuelLog, ReductionTarget, Tree, WasteLog


@admin.register(EmissionFactor)
class EmissionFactorAdmin(admin.ModelAdmin):
    list_display = ("activity", "scope", "value", "activity_unit", "valid_from", "version", "source")
    list_filter = ("scope", "activity")


@admin.register(FuelLog)
class FuelLogAdmin(admin.ModelAdmin):
    list_display = ("date", "category", "activity", "quantity", "asset")
    list_filter = ("category", "activity")


@admin.register(WasteLog)
class WasteLogAdmin(admin.ModelAdmin):
    list_display = ("date", "category", "disposal", "weight_kg", "building")
    list_filter = ("category", "disposal")


admin.site.register(CommuteSurvey)
admin.site.register(Tree)
admin.site.register(ReductionTarget)
