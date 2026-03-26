"""
Custom User model with rating, games_played, games_won.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with ELO rating and game stats."""

    rating = models.IntegerField(default=1000, db_index=True)
    games_played = models.IntegerField(default=0)
    games_won = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    # Social account linking (optional) — used for friend suggestions (Facebook) / identity (TikTok).
    facebook_id = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="Facebook app-scoped user id when linked.",
    )
    tiktok_open_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="TikTok open_id when linked via Login Kit.",
    )

    class Meta:
        db_table = "users_user"
