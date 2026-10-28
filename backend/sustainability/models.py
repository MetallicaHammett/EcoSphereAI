"""Carbon accounting inputs that are logged rather than metered: fuels, waste, commuting, trees, targets."""

from django.conf import settings
from django.db import models


class Activity(models.TextChoices):
    ELECTRICITY_GRID = "electricity_grid", "Grid electricity"
    DIESEL = "diesel", "Diesel"
    PETROL = "petrol", "Petrol"
    LPG = "lpg", "LPG"
    REFRIGERANT_R410A = "refrigerant_r410a", "Refrigerant R-410A"
    REFRIGERANT_R32 = "refrigerant_r32", "Refrigerant R-32"
    REFRIGERANT_R22 = "refrigerant_r22", "Refrigerant R-22"
    WATER_SUPPLY = "water_supply", "Water supply and treatment"
    WASTE_LANDFILL = "waste_landfill", "Waste to landfill"
    WASTE_RECYCLED = "waste_recycled", "Waste recycled"
    WASTE_COMPOSTED = "waste_composted", "Waste composted"
    WASTE_BIOGAS = "waste_biogas", "Waste to biogas"
    WASTE_INCINERATED = "waste_incinerated", "Waste incinerated"
    COMMUTE_CAR = "commute_car", "Commute - car"
    COMMUTE_TWO_WHEELER = "commute_two_wheeler", "Commute - two-wheeler"
    COMMUTE_BUS = "commute_bus", "Commute - bus"
    COMMUTE_AUTO = "commute_auto", "Commute - auto-rickshaw"
    COMMUTE_TRAIN = "commute_train", "Commute - metro / train"
    COMMUTE_EV = "commute_ev", "Commute - electric two-wheeler"
    COMMUTE_WALK = "commute_walk", "Commute - walking"
    COMMUTE_CYCLE = "commute_cycle", "Commute - cycling"


class EmissionFactor(models.Model):
    """
    Version-controlled emission factor. A new value is a new row with a later ``valid_from``;
    history is never overwritten, so past results stay reproducible.
    """

    activity = models.CharField(max_length=30, choices=Activity.choices)
    scope = models.PositiveSmallIntegerField(choices=[(1, "Scope 1"), (2, "Scope 2"), (3, "Scope 3")])
    value = models.FloatField(help_text="kg CO2e per activity unit")
    activity_unit = models.CharField(max_length=20)
    source = models.CharField(max_length=255)
    valid_from = models.DateField()
    version = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["activity", "-valid_from"]
        constraints = [models.UniqueConstraint(fields=["activity", "valid_from"], name="unique_factor_per_date")]

    def __str__(self):
        return f"{self.get_activity_display()} v{self.version}: {self.value} kg/{self.activity_unit}"


class FuelLog(models.Model):
    """Scope 1 direct emissions: generators, fleet, canteen/lab LPG and refrigerant top-ups."""

    class Category(models.TextChoices):
        GENERATOR = "generator", "Diesel generators"
        FLEET = "fleet", "Campus fleet"
        CANTEEN = "canteen", "Canteen & labs (LPG)"
        REFRIGERANT = "refrigerant", "Refrigerant leakage"

    FUEL_ACTIVITIES = [Activity.DIESEL, Activity.PETROL, Activity.LPG, Activity.REFRIGERANT_R410A,
                       Activity.REFRIGERANT_R32, Activity.REFRIGERANT_R22]

    date = models.DateField()
    category = models.CharField(max_length=20, choices=Category.choices)
    activity = models.CharField(max_length=30, choices=[(a.value, a.label) for a in FUEL_ACTIVITIES])
    quantity = models.FloatField(help_text="Litres for liquid fuels, kg for LPG and refrigerants")
    asset = models.CharField(max_length=120, blank=True, help_text="Vehicle number, generator ID, kitchen...")
    distance_km = models.FloatField(null=True, blank=True, help_text="Fleet only")
    building = models.ForeignKey("monitoring.Building", null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-date", "-id"]


class WasteLog(models.Model):
    class Category(models.TextChoices):
        WET = "wet", "Wet / organic"
        DRY = "dry", "Dry"
        RECYCLABLE = "recyclable", "Recyclable"
        EWASTE = "ewaste", "E-waste"
        HAZARDOUS = "hazardous", "Hazardous"

    class Disposal(models.TextChoices):
        LANDFILL = "landfill", "Landfill"
        RECYCLED = "recycled", "Recycled"
        COMPOSTED = "composted", "Composted"
        BIOGAS = "biogas", "Biogas"
        INCINERATED = "incinerated", "Incinerated (authorised)"

    DIVERTED = {Disposal.RECYCLED, Disposal.COMPOSTED, Disposal.BIOGAS}

    date = models.DateField()
    building = models.ForeignKey("monitoring.Building", null=True, blank=True, on_delete=models.SET_NULL)
    category = models.CharField(max_length=20, choices=Category.choices)
    disposal = models.CharField(max_length=20, choices=Disposal.choices)
    weight_kg = models.FloatField()
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-date", "-id"]


class CommuteSurvey(models.Model):
    class Mode(models.TextChoices):
        WALK = "walk", "Walking"
        CYCLE = "cycle", "Cycling"
        BUS = "bus", "Bus / campus shuttle"
        TRAIN = "train", "Metro / train"
        TWO_WHEELER = "two_wheeler", "Petrol two-wheeler"
        EV = "ev", "Electric two-wheeler"
        AUTO = "auto", "Auto-rickshaw"
        CAR = "car", "Car"

    SUSTAINABLE = {Mode.WALK, Mode.CYCLE, Mode.BUS, Mode.TRAIN, Mode.EV}

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="commutes")
    respondent = models.CharField(max_length=10, choices=[("student", "Student"), ("staff", "Staff")],
                                  default="student")
    mode = models.CharField(max_length=20, choices=Mode.choices)
    distance_km = models.FloatField(help_text="One-way distance")
    days_per_week = models.PositiveSmallIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def activity(self):
        return f"commute_{self.mode}"


class Tree(models.Model):
    species = models.CharField(max_length=120)
    zone = models.CharField(max_length=120)
    count = models.PositiveIntegerField()
    planted_year = models.PositiveIntegerField(null=True, blank=True)
    sequestration_kg_per_tree = models.FloatField(help_text="Conservative kg CO2 per tree per year")
    canopy_m2_per_tree = models.FloatField(default=0)

    class Meta:
        ordering = ["species"]


class ReductionTarget(models.Model):
    name = models.CharField(max_length=160)
    baseline_year = models.PositiveIntegerField()
    baseline_tco2e = models.FloatField()
    target_year = models.PositiveIntegerField()
    reduction_pct = models.FloatField(help_text="Percentage reduction from baseline by target year")

    class Meta:
        ordering = ["target_year"]

    @property
    def target_tco2e(self):
        return self.baseline_tco2e * (1 - self.reduction_pct / 100)
