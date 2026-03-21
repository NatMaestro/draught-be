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

    class Meta:
        db_table = "users_user"
