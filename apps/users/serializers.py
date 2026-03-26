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
    facebook_linked = serializers.SerializerMethodField()
    tiktok_linked = serializers.SerializerMethodField()

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
            "facebook_linked",
            "tiktok_linked",
        ]

    def get_facebook_linked(self, obj: User) -> bool:
        return bool(obj.facebook_id)

    def get_tiktok_linked(self, obj: User) -> bool:
        return bool(obj.tiktok_open_id)
