"""In-app notifications + best-effort Web Push."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model

from .models import Friendship, FriendRequest, Notification, PushSubscription
from .ws_broadcast import broadcast_social_user

logger = logging.getLogger(__name__)
User = get_user_model()


def _ordered_pair(user1: User, user2: User) -> tuple[User, User]:
    if user1.id < user2.id:
        return user1, user2
    return user2, user1


def are_friends(u1: User, u2: User) -> bool:
    a, b = _ordered_pair(u1, u2)
    return Friendship.objects.filter(user_a=a, user_b=b).exists()


def create_notification(
    *,
    recipient: User,
    kind: str,
    title: str,
    body: str = "",
    payload: dict[str, Any] | None = None,
) -> Notification:
    n = Notification.objects.create(
        recipient=recipient,
        kind=kind,
        title=title,
        body=body,
        payload=payload or {},
    )
    send_web_push(recipient, title, body, payload or {})
    return n


def send_web_push(
    user: User,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> None:
    private_key = getattr(settings, "VAPID_PRIVATE_KEY", "") or ""
    if not private_key.strip():
        return

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush not installed; skipping Web Push")
        return

    subject = getattr(settings, "VAPID_SUBJECT", "mailto:support@example.com")
    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "data": data or {},
        }
    )
    subs = list(PushSubscription.objects.filter(user=user))
    if not subs:
        return

    stale_ids: list[str] = []
    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=private_key.strip(),
                vapid_claims={"sub": subject},
            )
        except WebPushException as e:
            status = getattr(e, "response", None)
            code = getattr(status, "status_code", None) if status is not None else None
            if code in (404, 410):
                stale_ids.append(str(sub.id))
            else:
                logger.warning("Web Push failed: %s", e)

    if stale_ids:
        PushSubscription.objects.filter(id__in=stale_ids).delete()


def notify_game_challenge_created(ch) -> None:
    from apps.games.models import GameChallenge

    assert isinstance(ch, GameChallenge)
    sender = ch.from_user
    title = "Game invite"
    body = f"{sender.username} challenged you to a game."
    create_notification(
        recipient=ch.to_user,
        kind=Notification.Kind.GAME_CHALLENGE,
        title=title,
        body=body,
        payload={"challenge_id": str(ch.id), "from_user_id": sender.id},
    )


def notify_game_challenge_accepted(ch, game) -> None:
    from apps.games.models import GameChallenge

    assert isinstance(ch, GameChallenge)
    accepter = ch.to_user
    title = "Challenge accepted"
    body = f"{accepter.username} accepted your invite."
    create_notification(
        recipient=ch.from_user,
        kind=Notification.Kind.CHALLENGE_ACCEPTED,
        title=title,
        body=body,
        payload={
            "challenge_id": str(ch.id),
            "game_id": str(game.id),
            "to_user_id": accepter.id,
        },
    )


def notify_game_challenge_declined(ch) -> None:
    from apps.games.models import GameChallenge

    assert isinstance(ch, GameChallenge)
    decliner = ch.to_user
    title = "Challenge declined"
    body = f"{decliner.username} declined your invite."
    create_notification(
        recipient=ch.from_user,
        kind=Notification.Kind.CHALLENGE_DECLINED,
        title=title,
        body=body,
        payload={"challenge_id": str(ch.id), "to_user_id": decliner.id},
    )


def notify_friend_request(fr: FriendRequest) -> None:
    assert isinstance(fr, FriendRequest)
    title = "Friend request"
    body = f"{fr.from_user.username} wants to be friends."
    create_notification(
        recipient=fr.to_user,
        kind=Notification.Kind.FRIEND_REQUEST,
        title=title,
        body=body,
        payload={"friend_request_id": str(fr.id), "from_user_id": fr.from_user_id},
    )
    broadcast_social_user(
        fr.to_user_id,
        {
            "type": "social",
            "action": "friend_request_received",
            "friend_request_id": str(fr.id),
            "from_user_id": fr.from_user_id,
        },
    )


def notify_friend_accepted(*, accepter: User, requester: User) -> None:
    title = "Friends"
    body = f"{accepter.username} accepted your friend request."
    create_notification(
        recipient=requester,
        kind=Notification.Kind.FRIEND_ACCEPTED,
        title=title,
        body=body,
        payload={"user_id": accepter.id},
    )
    broadcast_social_user(
        requester.id,
        {"type": "social", "action": "friend_accepted", "user_id": accepter.id},
    )


def add_friendship(user1: User, user2: User) -> Friendship:
    a, b = _ordered_pair(user1, user2)
    obj, _ = Friendship.objects.get_or_create(user_a=a, user_b=b)
    return obj
