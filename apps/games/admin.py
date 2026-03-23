from django.contrib import admin

from .models import Game, GameChallenge, GameChatMessage, Move


class MoveInline(admin.TabularInline):
    model = Move
    extra = 0
    readonly_fields = (
        "from_row",
        "from_col",
        "to_row",
        "to_col",
        "captured_row",
        "captured_col",
        "created_at",
    )
    raw_id_fields = ("player",)
    can_delete = True


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "current_turn",
        "player_one",
        "player_two",
        "is_ai_game",
        "is_ranked",
        "is_local_2p",
        "winner",
        "created_at",
    )
    list_filter = ("status", "is_ai_game", "is_ranked", "is_local_2p", "use_clock")
    search_fields = (
        "id",
        "player_one__username",
        "player_two__username",
    )
    readonly_fields = ("id", "board_state", "created_at", "finished_at")
    raw_id_fields = ("player_one", "player_two", "winner")
    inlines = [MoveInline]
    date_hierarchy = "created_at"


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("id", "game", "player", "from_row", "from_col", "to_row", "to_col", "created_at")
    list_filter = ("created_at",)
    search_fields = ("game__id", "player__username")
    readonly_fields = ("created_at",)
    raw_id_fields = ("game", "player")


@admin.register(GameChallenge)
class GameChallengeAdmin(admin.ModelAdmin):
    list_display = ("id", "from_user", "to_user", "status", "rematch_game", "created_at")
    list_filter = ("status", "created_at")
    search_fields = (
        "id",
        "from_user__username",
        "to_user__username",
    )
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("from_user", "to_user", "rematch_game")
    date_hierarchy = "created_at"


@admin.register(GameChatMessage)
class GameChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "game", "user", "guest_name", "body_preview", "created_at")
    list_filter = ("created_at",)
    search_fields = ("body", "game__id", "user__username", "guest_name")
    readonly_fields = ("created_at",)
    raw_id_fields = ("game", "user")
    date_hierarchy = "created_at"

    @admin.display(description="Body")
    def body_preview(self, obj):
        text = (obj.body or "").strip()
        if len(text) > 80:
            return text[:77] + "…"
        return text
