from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "rating",
            "games_played",
            "games_won",
            "created_at",
        ]
        read_only_fields = ["id", "rating", "games_played", "games_won", "created_at"]


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "rating",
            "games_played",
            "games_won",
            "created_at",
        ]
