from django.urls import path

from . import views

urlpatterns = [
    path("notifications/", views.NotificationListView.as_view()),
    path(
        "notifications/unread-count/",
        views.UnreadNotificationCountView.as_view(),
    ),
    path(
        "notifications/mark-read/",
        views.NotificationMarkReadView.as_view(),
    ),
    path("friends/", views.FriendListView.as_view()),
    path("recommended-match/", views.RecommendedMatchView.as_view()),
    path("friends/requests/", views.FriendRequestCreateView.as_view()),
    path(
        "friends/requests/incoming/",
        views.FriendRequestIncomingListView.as_view(),
    ),
    path(
        "friends/requests/outgoing/",
        views.FriendRequestOutgoingListView.as_view(),
    ),
    path(
        "friends/requests/<uuid:request_id>/accept/",
        views.FriendRequestAcceptView.as_view(),
    ),
    path(
        "friends/requests/<uuid:request_id>/decline/",
        views.FriendRequestDeclineView.as_view(),
    ),
    path(
        "friends/requests/<uuid:request_id>/cancel/",
        views.FriendRequestCancelView.as_view(),
    ),
    path("opponents/recent/", views.RecentOpponentsView.as_view()),
    path("link/facebook/", views.LinkFacebookView.as_view()),
    path("unlink/facebook/", views.UnlinkFacebookView.as_view()),
    path("suggestions/facebook/", views.FacebookFriendSuggestionsView.as_view()),
    path("tiktok/config/", views.TikTokOAuthConfigView.as_view()),
    path("link/tiktok/", views.LinkTikTokView.as_view()),
    path("unlink/tiktok/", views.UnlinkTikTokView.as_view()),
    path(
        "push/vapid-public-key/",
        views.VapidPublicKeyView.as_view(),
    ),
    path("push/subscribe/", views.PushSubscribeView.as_view()),
    path("push/unsubscribe/", views.PushUnsubscribeView.as_view()),
]
