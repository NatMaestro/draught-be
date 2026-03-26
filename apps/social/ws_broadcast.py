"""Real-time fan-out to users subscribed on `UserSocialConsumer` (group `user_social_{id}`)."""

from __future__ import annotations

from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_social_user(user_id: int, payload: dict[str, Any]) -> None:
    """Send a JSON-serializable payload to one user's social WebSocket (if connected)."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    async_to_sync(channel_layer.group_send)(
        f"user_social_{user_id}",
        {"type": "social.notify", "data": payload},
    )
