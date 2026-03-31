from django.utils import timezone
from rest_framework import serializers

from apps.users.models import User

from .models import Game, GameChallenge, Move
from .services import can_undo_game, get_moves_payload_for_client, match_state_public


class PlayerPublicSerializer(serializers.ModelSerializer):
    """Minimal user info for game screens (seat labels, avatars)."""

    class Meta:
        model = User
        fields = ["id", "username"]


class GameSerializer(serializers.ModelSerializer):
    can_undo = serializers.SerializerMethodField()
    moves = serializers.SerializerMethodField()
    match = serializers.SerializerMethodField()
    player_one = PlayerPublicSerializer(read_only=True)
    player_two = PlayerPublicSerializer(read_only=True)
    server_now = serializers.SerializerMethodField()

    class Meta:
        model = Game
        fields = [
            "id",
            "player_one",
            "player_two",
            "board_state",
            "current_turn",
            "status",
            "winner",
            "is_ranked",
            "is_ai_game",
            "is_local_2p",
            "ai_difficulty",
            "created_at",
            "finished_at",
            "use_clock",
            "time_control_sec",
            "p1_time_remaining_sec",
            "p2_time_remaining_sec",
            "turn_started_at",
            "server_now",
            "can_undo",
            "moves",
            "match",
        ]
        read_only_fields = fields

    def get_server_now(self, obj: Game) -> str:
        return timezone.now().isoformat()

    def get_can_undo(self, obj: Game) -> bool:
        return can_undo_game(obj)

    def get_moves(self, obj: Game) -> list[dict]:
        """Ordered plies with captures for replay / move list."""
        return get_moves_payload_for_client(obj)

    def get_match(self, obj: Game) -> dict | None:
        return match_state_public(obj)


class GameListSerializer(serializers.ModelSerializer):
    player_one = PlayerPublicSerializer(read_only=True)
    player_two = PlayerPublicSerializer(read_only=True)
    move_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Game
        fields = [
            "id",
            "status",
            "current_turn",
            "winner",
            "is_ai_game",
            "is_ranked",
            "is_local_2p",
            "created_at",
            "finished_at",
            "player_one",
            "player_two",
            "move_count",
        ]
        read_only_fields = fields


class GameChallengeSerializer(serializers.ModelSerializer):
    from_user = PlayerPublicSerializer(read_only=True)
    to_user = PlayerPublicSerializer(read_only=True)
    game_id = serializers.SerializerMethodField()

    class Meta:
        model = GameChallenge
        fields = [
            "id",
            "from_user",
            "to_user",
            "rematch_game",
            "is_match",
            "is_ranked",
            "status",
            "created_at",
            "game_id",
        ]
        read_only_fields = fields

    def get_game_id(self, obj):
        if obj.result_game_id:
            return str(obj.result_game_id)
        return None


class GameChallengeCreateSerializer(serializers.Serializer):
    to_user_id = serializers.IntegerField(min_value=1)
    rematch_game_id = serializers.UUIDField(required=False, allow_null=True)
    is_match = serializers.BooleanField(required=False, default=False)
    is_ranked = serializers.BooleanField(required=False, default=False)


class MoveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Move
        fields = [
            "id",
            "game",
            "player",
            "from_row",
            "from_col",
            "to_row",
            "to_col",
            "captured_row",
            "captured_col",
            "created_at",
        ]
