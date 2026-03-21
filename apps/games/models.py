"""
Game and Move models.
"""

import uuid
from django.db import models
from django.conf import settings


class Game(models.Model):
    """Game session with board state."""

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        ACTIVE = "active", "Active"
        FINISHED = "finished", "Finished"
        ABANDONED = "abandoned", "Abandoned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player_one = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="games_as_player_one",
        null=True,
        blank=True,
    )
    player_two = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="games_as_player_two",
        null=True,
        blank=True,
    )
    board_state = models.JSONField(default=list)  # 10x10 array
    current_turn = models.IntegerField(default=1)  # 1 or 2
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
        db_index=True,
    )
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="victories",
    )
    is_ranked = models.BooleanField(default=False)
    is_ai_game = models.BooleanField(default=False)
    # Same-device hot-seat (no second account). Used for undo eligibility.
    is_local_2p = models.BooleanField(default=False)
    ai_difficulty = models.CharField(
        max_length=10,
        blank=True,
        choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "games_game"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Game {self.id}"


class GameChatMessage(models.Model):
    """In-game chat (WebSocket + optional history on join)."""

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="chat_messages")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="game_chat_messages",
    )
    guest_name = models.CharField(max_length=64, blank=True)
    body = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "games_gamechatmessage"
        ordering = ["created_at"]


class Move(models.Model):
    """Single move in a game."""

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="moves")
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    from_row = models.IntegerField()
    from_col = models.IntegerField()
    to_row = models.IntegerField()
    to_col = models.IntegerField()
    captured_row = models.IntegerField(null=True, blank=True)
    captured_col = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "games_move"
        ordering = ["created_at"]
