from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "rating", "games_played", "games_won", "is_staff", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email")
    ordering = ("-date_joined",)
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Draught stats", {"fields": ("rating", "games_played", "games_won")}),
    )
