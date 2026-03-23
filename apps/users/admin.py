from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "rating",
        "games_played",
        "games_won",
        "is_staff",
        "is_active",
        "date_joined",
        "created_at",
    )
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email")
    ordering = ("-date_joined",)
    filter_horizontal = ("groups", "user_permissions")
    # Standard auth read-only fields + custom User.created_at (BaseUserAdmin.readonly_fields
    # is not reliable at subclass definition time in all Django versions).
    readonly_fields = ("password", "last_login", "date_joined", "created_at")

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Draught stats", {"fields": ("rating", "games_played", "games_won")}),
        ("Timestamps", {"fields": ("created_at",)}),
    )
