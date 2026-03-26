from rest_framework import serializers

from apps.games.serializers import PlayerPublicSerializer

from .models import FriendRequest, Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Adds `game_status` for challenge_accepted rows so the client can hide Join when the match ended."""

    game_status = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "kind",
            "title",
            "body",
            "read_at",
            "payload",
            "game_status",
            "created_at",
        ]
        read_only_fields = fields

    def get_game_status(self, obj):
        if obj.kind != Notification.Kind.CHALLENGE_ACCEPTED:
            return None
        payload = obj.payload or {}
        gid = payload.get("game_id")
        if not gid:
            return None
        from apps.games.models import Game

        g = Game.objects.filter(id=gid).only("status").first()
        return g.status if g else None


class FriendRequestSerializer(serializers.ModelSerializer):
    from_user = PlayerPublicSerializer(read_only=True)
    to_user = PlayerPublicSerializer(read_only=True)

    class Meta:
        model = FriendRequest
        fields = [
            "id",
            "from_user",
            "to_user",
            "status",
            "created_at",
        ]
        read_only_fields = fields


class FriendRequestCreateSerializer(serializers.Serializer):
    to_user_id = serializers.IntegerField(min_value=1)


class PushSubscribeSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=2048)
    keys = serializers.DictField(child=serializers.CharField())
    # keys: p256dh, auth

    def validate_keys(self, value):
        if "p256dh" not in value or "auth" not in value:
            raise serializers.ValidationError("keys must include p256dh and auth")
        return value


class PushUnsubscribeSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=2048)


class LinkFacebookSerializer(serializers.Serializer):
    access_token = serializers.CharField()


class FacebookFriendSuggestionsSerializer(serializers.Serializer):
    """Fresh user access token (same as Facebook Login) to read `/me/friends`."""

    access_token = serializers.CharField()


class LinkTikTokSerializer(serializers.Serializer):
    code = serializers.CharField()
    redirect_uri = serializers.URLField(max_length=2048)
