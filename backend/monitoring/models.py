"""Physical campus, IoT devices and the readings they send (sensing + data platform layers)."""

import secrets

from django.conf import settings
from django.db import models


class CampusSettings(models.Model):
    """Single row holding the organisational boundary, population and tariffs."""

    name = models.CharField(max_length=200, default="SRM IST Vadapalani Campus")
    student_count = models.PositiveIntegerField(default=5200)
    staff_count = models.PositiveIntegerField(default=650)
    baseline_year = models.PositiveIntegerField(default=2025)
    electricity_tariff = models.FloatField(default=9.0, help_text="INR per kWh")
    diesel_price = models.FloatField(default=92.0, help_text="INR per litre")
    water_tariff = models.FloatField(default=60.0, help_text="INR per kL")
    green_power_share = models.FloatField(
        default=0.0, help_text="Share (0-1) of grid electricity bought as certified renewable power (market-based Scope 2)"
    )
    boundary_notes = models.TextField(
        blank=True,
        default="Includes all academic blocks, laboratories, library, hostels, food court, sports complex "
        "and campus fleet. Excludes leased retail kiosks.",
    )

    class Meta:
        verbose_name_plural = "campus settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def population(self):
        return self.student_count + self.staff_count


class Building(models.Model):
    class Type(models.TextChoices):
        ACADEMIC = "academic", "Academic block"
        LAB = "lab", "Laboratory"
        LIBRARY = "library", "Library"
        ADMIN = "admin", "Administration"
        HOSTEL = "hostel", "Hostel"
        CANTEEN = "canteen", "Canteen / Food court"
        SPORTS = "sports", "Sports facility"

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=20, unique=True)
    type = models.CharField(max_length=20, choices=Type.choices)
    area_m2 = models.FloatField()
    occupants = models.PositiveIntegerField(help_text="Typical daily occupants or residents")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_residential(self):
        return self.type == self.Type.HOSTEL


def _new_key():
    return secrets.token_hex(20)


class Gateway(models.Model):
    """Edge gateway that buffers readings and forwards them to the platform."""

    name = models.CharField(max_length=120)
    key = models.CharField(max_length=64, unique=True, default=_new_key)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class Meter(models.Model):
    class Kind(models.TextChoices):
        ELECTRICITY = "electricity", "Grid electricity (kWh)"
        SOLAR = "solar", "Solar generation (kWh)"
        WATER = "water", "Water consumption (kL)"
        WATER_SOURCE = "water_source", "Water supply source (kL)"

    class Source(models.TextChoices):
        NONE = "", "-"
        MUNICIPAL = "municipal", "Municipal supply"
        BOREWELL = "borewell", "Borewell"
        RAINWATER = "rainwater", "Rainwater harvesting"
        RECYCLED = "recycled", "STP recycled water"

    building = models.ForeignKey(Building, null=True, blank=True, on_delete=models.CASCADE, related_name="meters")
    gateway = models.ForeignKey(Gateway, null=True, blank=True, on_delete=models.SET_NULL, related_name="meters")
    name = models.CharField(max_length=120)
    serial = models.CharField(max_length=60, unique=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    source = models.CharField(max_length=20, choices=Source.choices, blank=True, default="")
    unit = models.CharField(max_length=10)
    capacity = models.FloatField(default=0, help_text="Installed capacity, e.g. kWp for solar")
    max_value = models.FloatField(
        default=0, help_text="Largest physically possible consumption per hour; 0 disables the check"
    )
    is_active = models.BooleanField(default=True)
    last_reading_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return f"{self.name} ({self.serial})"


class Reading(models.Model):
    """Consumption (or generation) over ``interval_minutes`` starting at ``timestamp``."""

    class Quality(models.TextChoices):
        OK = "ok", "OK"
        SUSPECT = "suspect", "Suspect"
        ESTIMATED = "estimated", "Estimated"

    meter = models.ForeignKey(Meter, on_delete=models.CASCADE, related_name="readings")
    timestamp = models.DateTimeField()
    value = models.FloatField()
    interval_minutes = models.PositiveSmallIntegerField(default=60)
    quality = models.CharField(max_length=10, choices=Quality.choices, default=Quality.OK)

    class Meta:
        indexes = [
            models.Index(fields=["meter", "timestamp"]),
            models.Index(fields=["timestamp"]),
        ]


class EnvReading(models.Model):
    """Indoor environment: temperature, humidity, CO2 and occupancy."""

    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="env_readings")
    timestamp = models.DateTimeField()
    temperature = models.FloatField()
    humidity = models.FloatField()
    co2_ppm = models.FloatField()
    occupancy = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["building", "timestamp"])]


class WeatherReading(models.Model):
    timestamp = models.DateTimeField(db_index=True)
    temperature = models.FloatField()
    humidity = models.FloatField()
    irradiance = models.FloatField(help_text="W/m2")
    rainfall_mm = models.FloatField(default=0)


class CalendarDay(models.Model):
    """Academic calendar: holidays and vacations change the expected load."""

    class Kind(models.TextChoices):
        HOLIDAY = "holiday", "Holiday"
        VACATION = "vacation", "Vacation"
        EXAM = "exam", "Examination"

    date = models.DateField(unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    label = models.CharField(max_length=120)

    class Meta:
        ordering = ["date"]


class Alert(models.Model):
    """An anomaly or fault raised by the analytics layer; doubles as a work order."""

    class Category(models.TextChoices):
        ENERGY = "energy", "Energy"
        WATER = "water", "Water"
        ENVIRONMENT = "environment", "Indoor environment"
        DATA = "data_quality", "Data quality"

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"

    building = models.ForeignKey(Building, null=True, blank=True, on_delete=models.CASCADE, related_name="alerts")
    meter = models.ForeignKey(Meter, null=True, blank=True, on_delete=models.CASCADE, related_name="alerts")
    category = models.CharField(max_length=20, choices=Category.choices)
    alert_type = models.CharField(max_length=30)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM)
    title = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="alerts"
    )
    notes = models.TextField(blank=True)
    excess_quantity = models.FloatField(default=0)
    excess_unit = models.CharField(max_length=10, blank=True)
    estimated_cost = models.FloatField(default=0)
    dedupe_key = models.CharField(max_length=120, unique=True)
    occurred_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
