"""
Matchmaking using Redis queues.

Casual: FIFO (first compatible joiner pairs with next).

Ranked: FIFO among players whose ratings are within an allowed gap. The gap
widens the longer either player has been waiting (similar to Chess.com ranges
expanding if no opponent is found).
"""

from __future__ import annotations

import json
import time

from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

try:
    import redis
except ImportError:
    redis = None

REDIS_URL = getattr(settings, "REDIS_URL", "redis://127.0.0.1:6379/0")
QUEUE_RANKED = "matchmaking:ranked"
QUEUE_CASUAL = "matchmaking:casual"
# After a game is created, both players can read their assigned game id (esp. player who was waiting first).
MATCH_READY_KEY = "matchmaking:ready:{user_id}"
MATCH_READY_TTL_SEC = 180


def _get_redis():
    if redis is None:
        return None
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        return r
    except Exception:
        return None


def is_matchmaking_redis_available() -> bool:
    """True if Redis is installed and responds to ping at REDIS_URL."""
    return _get_redis() is not None


def ranked_effective_delta_for_elapsed(elapsed_sec: float) -> int:
    """
    Max rating difference allowed for a player who has been waiting `elapsed_sec`.

    Starts at MATCHMAKING_RANKED_INITIAL_DELTA, adds MATCHMAKING_RANKED_EXPAND_STEP
    every MATCHMAKING_RANKED_EXPAND_EVERY_SEC, capped at MATCHMAKING_RANKED_MAX_DELTA.
    """
    initial = int(getattr(settings, "MATCHMAKING_RANKED_INITIAL_DELTA", 150))
    max_d = int(getattr(settings, "MATCHMAKING_RANKED_MAX_DELTA", 500))
    every = max(1, int(getattr(settings, "MATCHMAKING_RANKED_EXPAND_EVERY_SEC", 15)))
    step = int(getattr(settings, "MATCHMAKING_RANKED_EXPAND_STEP", 25))
    if elapsed_sec <= 0:
        return min(max_d, initial)
    tiers = int(elapsed_sec // every)
    return min(max_d, initial + tiers * step)


def _ranked_pair_allowed(
    rating_a: int,
    rating_b: int,
    elapsed_a_sec: float,
    elapsed_b_sec: float,
) -> bool:
    """True if two players are within the combined expanded window."""
    d_a = ranked_effective_delta_for_elapsed(elapsed_a_sec)
    d_b = ranked_effective_delta_for_elapsed(elapsed_b_sec)
    max_d = int(getattr(settings, "MATCHMAKING_RANKED_MAX_DELTA", 500))
    # If either side has waited a long time, widen the pairing window (max of the two).
    d = min(max_d, max(d_a, d_b))
    return abs(int(rating_a) - int(rating_b)) <= d


def _parse_ranked_queue_item(raw: str) -> dict | None:
    """Parse ranked queue JSON; tolerate legacy `{\"user_id\": n}` entries."""
    try:
        o = json.loads(raw)
        uid = int(o.get("user_id", o))
        r = int(o.get("rating", getattr(settings, "ELO_INITIAL_RATING", 1000)))
        t = float(o.get("t", time.time()))
        tc = int(o.get("tc", 600))
        uc = bool(o.get("uc", True))
        return {"user_id": uid, "rating": r, "t": t, "tc": tc, "uc": uc, "_raw": raw}
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _add_to_ranked_queue(
    r,
    user_id: int,
    rating: int,
    *,
    time_control_sec: int = 600,
    use_clock: bool = True,
) -> bool:
    """
    Try to pair with the earliest queued player within the current rating window.
    Returns True if paired.
    """
    now = time.time()
    items = r.lrange(QUEUE_RANKED, 0, -1)
    for raw in items:
        b = _parse_ranked_queue_item(raw)
        if not b:
            continue
        elapsed_b = now - b["t"]
        elapsed_a = 0.0  # joiner just arrived
        if _ranked_pair_allowed(rating, b["rating"], elapsed_a, elapsed_b):
            r.lrem(QUEUE_RANKED, 1, raw)
            r.lpush(
                "matchmaking:pending",
                json.dumps(
                    {
                        "player1": b["user_id"],
                        "player2": user_id,
                        "ranked": True,
                        "time_control_sec": b.get("tc", 600),
                        "use_clock": b.get("uc", True),
                    },
                ),
            )
            return True
    # No compatible opponent: join the tail
    r.rpush(
        QUEUE_RANKED,
        json.dumps(
            {
                "user_id": user_id,
                "rating": int(rating),
                "t": now,
                "tc": time_control_sec,
                "uc": use_clock,
            },
        ),
    )
    return False


def _add_to_casual_queue(
    r,
    user_id: int,
    *,
    time_control_sec: int = 600,
    use_clock: bool = True,
) -> bool:
    """FIFO casual queue; first player's clock settings apply to the created game."""
    data = json.dumps(
        {"user_id": user_id, "tc": time_control_sec, "uc": use_clock},
    )
    opponent_raw = r.lpop(QUEUE_CASUAL)
    if opponent_raw:
        try:
            opp = json.loads(opponent_raw)
            opp_id = int(opp.get("user_id", opp))
            tc = int(opp.get("tc", 600))
            uc = bool(opp.get("uc", True))
        except (json.JSONDecodeError, TypeError, ValueError):
            r.lpush(QUEUE_CASUAL, opponent_raw)
            r.rpush(QUEUE_CASUAL, data)
            return False
        r.lpush(
            "matchmaking:pending",
            json.dumps(
                {
                    "player1": opp_id,
                    "player2": user_id,
                    "ranked": False,
                    "time_control_sec": tc,
                    "use_clock": uc,
                },
            ),
        )
        return True
    r.rpush(QUEUE_CASUAL, data)
    return False


def add_to_queue(
    user_id: int,
    ranked: bool,
    rating: int | None = None,
    *,
    time_control_sec: int = 600,
    use_clock: bool = True,
) -> bool:
    """
    Add user to matchmaking queue. Returns True if paired, False if queued.

    For ranked games, pass the user's current Elo ``rating`` (required for fair pairing).
    """
    r = _get_redis()
    if not r:
        return False
    if ranked:
        r_val = int(
            rating if rating is not None else getattr(settings, "ELO_INITIAL_RATING", 1000),
        )
        return _add_to_ranked_queue(
            r,
            user_id,
            r_val,
            time_control_sec=time_control_sec,
            use_clock=use_clock,
        )
    return _add_to_casual_queue(
        r,
        user_id,
        time_control_sec=time_control_sec,
        use_clock=use_clock,
    )


def remove_from_queue(user_id: int, ranked: bool) -> bool:
    """Remove user from queue. Returns True if removed."""
    r = _get_redis()
    if not r:
        return False
    queue = QUEUE_RANKED if ranked else QUEUE_CASUAL
    items = r.lrange(queue, 0, -1)
    for item in items:
        try:
            data = json.loads(item)
            if data.get("user_id") == user_id:
                r.lrem(queue, 1, item)
                return True
        except (json.JSONDecodeError, TypeError):
            continue
    return False


def notify_match_ready(game_id: str, player1_id: int, player2_id: int) -> None:
    """Let both players pick up game_id via GET /matchmaking/ready/ (polling)."""
    r = _get_redis()
    if not r:
        return
    for uid in (player1_id, player2_id):
        r.setex(
            MATCH_READY_KEY.format(user_id=uid),
            MATCH_READY_TTL_SEC,
            str(game_id),
        )


def get_and_clear_match_ready(user_id: int) -> str | None:
    """Return game id if this user was notified, then delete the key."""
    r = _get_redis()
    if not r:
        return None
    key = MATCH_READY_KEY.format(user_id=user_id)
    gid = r.get(key)
    if gid:
        r.delete(key)
    return gid


def get_pending_match(user_id: int) -> dict | None:
    """Check if user has a pending match (was just paired). Returns {player1, player2, ranked} or None."""
    r = _get_redis()
    if not r:
        return None
    items = r.lrange("matchmaking:pending", 0, -1)
    for item in items:
        try:
            data = json.loads(item)
            if data.get("player1") == user_id or data.get("player2") == user_id:
                r.lrem("matchmaking:pending", 1, item)
                return data
        except (json.JSONDecodeError, TypeError):
            continue
    return None
