from rest_framework import serializers
from .models import Game, Move
from .services import can_undo_game


class GameSerializer(serializers.ModelSerializer):
    can_undo = serializers.SerializerMethodField()

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
            "can_undo",
        ]
        read_only_fields = fields

    def get_can_undo(self, obj: Game) -> bool:
        return can_undo_game(obj)


class GameListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = [
            "id",
            "status",
            "current_turn",
            "winner",
            "is_ai_game",
            "created_at",
        ]


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
