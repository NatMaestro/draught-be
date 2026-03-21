"""
Matchmaking using Redis queues.
"""

import json
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


def _get_redis():
    if redis is None:
        return None
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        return r
    except Exception:
        return None


def add_to_queue(user_id: int, ranked: bool) -> bool:
    """Add user to matchmaking queue. Returns True if paired, False if queued."""
    r = _get_redis()
    if not r:
        return False
    queue = QUEUE_RANKED if ranked else QUEUE_CASUAL
    data = json.dumps({"user_id": user_id})
    opponent_raw = r.lpop(queue)
    if opponent_raw:
        try:
            opp = json.loads(opponent_raw)
            opp_id = int(opp.get("user_id", opp))
        except (json.JSONDecodeError, TypeError, ValueError):
            r.lpush(queue, opponent_raw)
            r.rpush(queue, data)
            return False
        r.lpush("matchmaking:pending", json.dumps({
            "player1": opp_id,
            "player2": user_id,
            "ranked": ranked,
        }))
        return True
    r.rpush(queue, data)
    return False


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
