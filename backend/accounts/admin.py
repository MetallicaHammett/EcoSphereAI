from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CampusUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Campus", {"fields": ("role", "department")}),)
    list_display = ("username", "email", "role", "department", "is_active")
    list_filter = ("role", "is_active")
