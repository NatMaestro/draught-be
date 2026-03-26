from django.contrib import admin

from .models import FriendRequest, Friendship, Notification, PushSubscription


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("id", "user_a", "user_b", "created_at")
    raw_id_fields = ("user_a", "user_b")


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "from_user", "to_user", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("from_user", "to_user")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "kind", "title", "read_at", "created_at")
    list_filter = ("kind",)
    raw_id_fields = ("recipient",)


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "endpoint", "created_at")
    raw_id_fields = ("user",)
