from django.contrib import admin

from .models import Alert, Building, CalendarDay, CampusSettings, EnvReading, Gateway, Meter, Reading, WeatherReading

admin.site.register(CampusSettings)
admin.site.register(CalendarDay)
admin.site.register(Gateway)


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "type", "area_m2", "occupants")


@admin.register(Meter)
class MeterAdmin(admin.ModelAdmin):
    list_display = ("name", "serial", "kind", "building", "is_active", "last_reading_at")
    list_filter = ("kind", "is_active")


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ("meter", "timestamp", "value", "quality")
    list_filter = ("quality", "meter__kind")
    date_hierarchy = "timestamp"


@admin.register(EnvReading)
class EnvReadingAdmin(admin.ModelAdmin):
    list_display = ("building", "timestamp", "temperature", "humidity", "co2_ppm", "occupancy")


@admin.register(WeatherReading)
class WeatherReadingAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "temperature", "humidity", "irradiance", "rainfall_mm")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "severity", "status", "occurred_on")
    list_filter = ("category", "severity", "status")
