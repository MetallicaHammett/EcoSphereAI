from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Campus user. The role drives what each person can see and change."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator / Sustainability officer"
        FACILITY = "facility", "Facility operations"
        COMMUNITY = "community", "Student / Staff"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.COMMUNITY)
    department = models.CharField(max_length=120, blank=True)

    @property
    def is_admin_role(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_operator(self):
        return self.is_admin_role or self.role == self.Role.FACILITY
