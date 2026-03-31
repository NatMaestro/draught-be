"""
Game and Move models.
"""

import uuid
from django.db import models
from django.conf import settings


class MatchSession(models.Model):
    """
    First-to-N mini-games (default 5). One Game row is reset between mini-games; this holds match totals.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        FINISHED = "finished", "Finished"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    p1_wins = models.PositiveSmallIntegerField(default=0)
    p2_wins = models.PositiveSmallIntegerField(default=0)
    target_wins = models.PositiveSmallIntegerField(
        default=5,
        help_text="Mini-games needed to win the match (e.g. 5).",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    match_winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="match_victories",
    )
    is_raw = models.BooleanField(
        default=False,
        help_text="True when the match ended with no mini-game wins for the loser (e.g. 5–0).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "games_matchsession"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Match {self.id} ({self.p1_wins}-{self.p2_wins})"


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
    # Engine mode id from client (e.g. easy, medium, expert, master, top_players).
    ai_difficulty = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    # Per-turn clock (server source of truth for online sync); bank resets after each move.
    use_clock = models.BooleanField(
        default=True,
        help_text="When False, no time limits and no clock deductions.",
    )
    time_control_sec = models.PositiveIntegerField(
        default=600,
        help_text="Seconds each player has per turn (e.g. 600 = 10 minutes); resets when turns change.",
    )
    p1_time_remaining_sec = models.FloatField(default=600.0)
    p2_time_remaining_sec = models.FloatField(default=600.0)
    turn_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the current turn began; active player's clock runs from here.",
    )
    match_session = models.ForeignKey(
        MatchSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="games",
        help_text="When set, board wins feed this match until target_wins is reached.",
    )

    class Meta:
        db_table = "games_game"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Game {self.id}"


class GameChallenge(models.Model):
    """User-to-user game invite (rematch / direct challenge)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="challenges_sent",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="challenges_received",
    )
    rematch_game = models.ForeignKey(
        "Game",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rematch_challenges",
    )
    # Game created when the invitee accepts; lets the challenger open the match from the API.
    result_game = models.ForeignKey(
        "Game",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="challenge_created_from",
    )
    is_match = models.BooleanField(
        default=False,
        help_text="First-to-five mini-games when the challenge is accepted.",
    )
    is_ranked = models.BooleanField(
        default=False,
        help_text="When True, the game from this invite uses Elo (per board or per match).",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "games_gamechallenge"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["to_user", "status"]),
        ]

    def __str__(self):
        return f"Challenge {self.id}"


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
