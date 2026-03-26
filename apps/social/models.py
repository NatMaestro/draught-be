import uuid

from django.conf import settings
from django.db import models


class Friendship(models.Model):
    """Undirected friendship: always stored with user_a_id < user_b_id."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_as_a",
    )
    user_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friendships_as_b",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_friendship"
        constraints = [
            models.UniqueConstraint(
                fields=["user_a", "user_b"],
                name="social_friendship_unique_pair",
            ),
            models.CheckConstraint(
                check=models.Q(user_a_id__lt=models.F("user_b_id")),
                name="social_friendship_ordered_ids",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_a_id} — {self.user_b_id}"


class FriendRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friend_requests_sent",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friend_requests_received",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_friendrequest"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["from_user", "to_user"],
                condition=models.Q(status="pending"),
                name="social_friendrequest_unique_pending_pair",
            ),
        ]

    def __str__(self):
        return f"{self.from_user_id} → {self.to_user_id} ({self.status})"


class Notification(models.Model):
    class Kind(models.TextChoices):
        GAME_CHALLENGE = "game_challenge", "Game challenge"
        CHALLENGE_ACCEPTED = "challenge_accepted", "Challenge accepted"
        CHALLENGE_DECLINED = "challenge_declined", "Challenge declined"
        FRIEND_REQUEST = "friend_request", "Friend request"
        FRIEND_ACCEPTED = "friend_accepted", "Friend accepted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_notifications",
    )
    kind = models.CharField(max_length=32, choices=Kind.choices, db_index=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    read_at = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_notification"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.kind} → {self.recipient_id}"


class PushSubscription(models.Model):
    """Web Push subscription (one row per browser/device endpoint)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.URLField(max_length=2048, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_pushsubscription"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} @ {self.endpoint[:48]}…"
