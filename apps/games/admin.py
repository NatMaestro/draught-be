from django.contrib import admin
from .models import Game, Move


class MoveInline(admin.TabularInline):
    model = Move
    extra = 0
    readonly_fields = ("from_row", "from_col", "to_row", "to_col", "captured_row", "captured_col", "created_at")
    can_delete = True


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "current_turn", "player_one", "player_two", "is_ai_game", "is_ranked", "winner", "created_at")
    list_filter = ("status", "is_ai_game", "is_ranked")
    search_fields = ("id",)
    readonly_fields = ("id", "board_state", "created_at", "finished_at")
    inlines = [MoveInline]
    date_hierarchy = "created_at"


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ("id", "game", "player", "from_row", "from_col", "to_row", "to_col", "created_at")
    list_filter = ("game",)
    search_fields = ("game__id",)
    readonly_fields = ("created_at",)
