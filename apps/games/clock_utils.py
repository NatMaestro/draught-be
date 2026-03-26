"""Server-side game clock: single source of truth for PvP time sync."""

from __future__ import annotations

from django.utils import timezone

from .models import Game


def _tc(game: Game) -> int:
    if not getattr(game, "use_clock", True):
        return 0
    v = int(game.time_control_sec or 600)
    return max(60, min(7200, v))


def init_clock_for_active_game(game: Game) -> None:
    """Set banks and turn start for a newly playable (ACTIVE) game."""
    if not getattr(game, "use_clock", True):
        game.p1_time_remaining_sec = 0.0
        game.p2_time_remaining_sec = 0.0
        game.turn_started_at = None
        return
    tc = float(_tc(game))
    game.p1_time_remaining_sec = tc
    game.p2_time_remaining_sec = tc
    game.turn_started_at = timezone.now()


def apply_clock_before_move(game: Game, player_num: int) -> None:
    """
    Subtract elapsed time since turn_started_at from the mover's remaining bank.
    Call before updating board / switching turns.
    """
    if not getattr(game, "use_clock", True):
        return
    now = timezone.now()
    tc = float(_tc(game))
    if game.turn_started_at is None:
        game.p1_time_remaining_sec = tc
        game.p2_time_remaining_sec = tc
        game.turn_started_at = now
        return
    elapsed = (now - game.turn_started_at).total_seconds()
    if player_num == 1:
        game.p1_time_remaining_sec = max(0.0, float(game.p1_time_remaining_sec) - elapsed)
    else:
        game.p2_time_remaining_sec = max(0.0, float(game.p2_time_remaining_sec) - elapsed)


def stamp_turn_started_now(game: Game) -> None:
    """Next player's turn just began."""
    game.turn_started_at = timezone.now()


def reset_per_turn_clock_for_player_to_move(game: Game) -> None:
    """
    Per-turn clock: each turn, the player to move gets a full `time_control_sec` bank.
    Call after switching `current_turn` (and before `stamp_turn_started_now`).
    """
    if not getattr(game, "use_clock", True):
        return
    tc = float(_tc(game))
    if game.current_turn == 1:
        game.p1_time_remaining_sec = tc
    else:
        game.p2_time_remaining_sec = tc


def freeze_clock_on_game_over(game: Game) -> None:
    """Stop the clock when the game ends."""
    game.turn_started_at = None


def active_player_remaining_seconds(game: Game) -> float | None:
    """
    Seconds remaining for the player to move (including elapsed time this turn).
    None if clock is off or game not clocked.
    """
    if not getattr(game, "use_clock", True):
        return None
    if game.turn_started_at is None:
        return float(
            game.p1_time_remaining_sec if game.current_turn == 1 else game.p2_time_remaining_sec,
        )
    elapsed = (timezone.now() - game.turn_started_at).total_seconds()
    if game.current_turn == 1:
        return max(0.0, float(game.p1_time_remaining_sec) - elapsed)
    return max(0.0, float(game.p2_time_remaining_sec) - elapsed)


def clock_payload(game: Game) -> dict:
    """
    Snapshot for API / WebSocket. Per-turn mode: the active player's bank counts down;
    `time_control_sec` is the full allowance each turn.
    """
    now = timezone.now()
    ts = game.turn_started_at
    if not getattr(game, "use_clock", True):
        return {
            "use_clock": False,
            "p1_time_remaining_sec": 0.0,
            "p2_time_remaining_sec": 0.0,
            "turn_started_at": None,
            "server_now": now.isoformat(),
            "time_control_sec": 0,
        }
    return {
        "use_clock": True,
        "p1_time_remaining_sec": float(game.p1_time_remaining_sec),
        "p2_time_remaining_sec": float(game.p2_time_remaining_sec),
        "turn_started_at": ts.isoformat() if ts else None,
        "server_now": now.isoformat(),
        "time_control_sec": _tc(game),
    }
