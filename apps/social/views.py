from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.games.models import Game
from apps.games.serializers import PlayerPublicSerializer

from .models import FriendRequest, Friendship, Notification, PushSubscription
from .external_accounts import (
    exchange_tiktok_oauth_code,
    extract_tiktok_open_id,
    fetch_facebook_friend_ids,
    verify_facebook_token,
)
from .serializers import (
    FacebookFriendSuggestionsSerializer,
    FriendRequestCreateSerializer,
    FriendRequestSerializer,
    LinkFacebookSerializer,
    LinkTikTokSerializer,
    NotificationSerializer,
    PushSubscribeSerializer,
    PushUnsubscribeSerializer,
)
from .ws_broadcast import broadcast_social_user
from .services import (
    add_friendship,
    are_friends,
    notify_friend_accepted,
    notify_friend_request,
)

User = get_user_model()


def _friend_users_for(user: User):
    """Users who are friends with `user` (either side of Friendship)."""
    pairs = Friendship.objects.filter(
        Q(user_a=user) | Q(user_b=user),
    ).select_related("user_a", "user_b")
    out = []
    for f in pairs:
        other = f.user_b if f.user_a_id == user.id else f.user_a
        out.append(other)
    return out


def _friend_user_ids(user: User) -> set[int]:
    return {u.id for u in _friend_users_for(user)}


class NotificationListView(generics.ListAPIView):
    """GET /api/social/notifications/ — newest first; optional ?unread=1."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user)
        if self.request.query_params.get("unread") in ("1", "true", "yes"):
            qs = qs.filter(read_at__isnull=True)
        return qs


class NotificationMarkReadView(APIView):
    """POST /api/social/notifications/mark-read/ — body: { \"ids\": [uuid, ...] } or mark all."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get("ids")
        if ids is None:
            Notification.objects.filter(
                recipient=request.user,
                read_at__isnull=True,
            ).update(read_at=timezone.now())
            return Response({"ok": True, "marked": "all"})
        if not isinstance(ids, list):
            return Response({"detail": "ids must be a list"}, status=400)
        n = (
            Notification.objects.filter(
                recipient=request.user,
                id__in=ids,
                read_at__isnull=True,
            ).update(read_at=timezone.now())
        )
        return Response({"ok": True, "marked": n})


def _head_to_head_stats(a: User, b: User) -> dict:
    """Finished online PvP games between two human accounts (not AI / local)."""
    qs = Game.objects.filter(
        status=Game.Status.FINISHED,
        is_ai_game=False,
        is_local_2p=False,
    ).filter(
        (Q(player_one=a) & Q(player_two=b))
        | (Q(player_one=b) & Q(player_two=a))
    )
    wins = losses = draws = 0
    for g in qs.iterator(chunk_size=200):
        wid = g.winner_id
        if wid is None:
            draws += 1
        elif wid == a.id:
            wins += 1
        else:
            losses += 1
    return {"wins": wins, "losses": losses, "draws": draws}


class FriendListView(APIView):
    """GET /api/social/friends/ — list of friend users."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = _friend_users_for(request.user)
        ser = PlayerPublicSerializer(users, many=True)
        return Response(ser.data)


class RecommendedMatchView(APIView):
    """
    GET /api/social/recommended-match/
    Pick a friend closest in Elo to the current user (within max_gap if possible),
    plus head-to-head record from finished online games.
    Query: max_gap (default 200, clamped 50–400).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            max_gap = int(request.query_params.get("max_gap", 200))
        except (TypeError, ValueError):
            max_gap = 200
        max_gap = max(50, min(max_gap, 400))

        friends = _friend_users_for(user)
        if not friends:
            return Response({"opponent": None})

        friends.sort(key=lambda f: abs(f.rating - user.rating))
        chosen = None
        in_band = False
        for f in friends:
            if abs(f.rating - user.rating) <= max_gap:
                chosen = f
                in_band = True
                break
        if chosen is None:
            chosen = friends[0]

        gap = abs(chosen.rating - user.rating)
        h2h = _head_to_head_stats(user, chosen)
        return Response(
            {
                "opponent": {
                    "id": chosen.id,
                    "username": chosen.username,
                    "rating": chosen.rating,
                },
                "rating_gap": gap,
                "in_rating_band": in_band,
                "head_to_head": h2h,
            }
        )


class FriendRequestCreateView(APIView):
    """POST /api/social/friends/requests/ — { to_user_id }."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = FriendRequestCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        to_id = ser.validated_data["to_user_id"]
        if to_id == request.user.id:
            return Response({"detail": "Cannot friend yourself"}, status=400)
        try:
            to_user = User.objects.get(pk=to_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)
        if are_friends(request.user, to_user):
            return Response({"detail": "Already friends"}, status=400)
        if FriendRequest.objects.filter(
            from_user=request.user,
            to_user=to_user,
            status=FriendRequest.Status.PENDING,
        ).exists():
            return Response({"detail": "Request already sent"}, status=400)
        if FriendRequest.objects.filter(
            from_user=to_user,
            to_user=request.user,
            status=FriendRequest.Status.PENDING,
        ).exists():
            return Response(
                {"detail": "They already sent you a request — accept that one."},
                status=400,
            )
        try:
            fr = FriendRequest.objects.create(
                from_user=request.user,
                to_user=to_user,
                status=FriendRequest.Status.PENDING,
            )
        except IntegrityError:
            return Response(
                {"detail": "Could not create request (duplicate or conflict)."},
                status=400,
            )
        notify_friend_request(fr)
        return Response(FriendRequestSerializer(fr).data, status=status.HTTP_201_CREATED)


class FriendRequestIncomingListView(generics.ListAPIView):
    serializer_class = FriendRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FriendRequest.objects.filter(
            to_user=self.request.user,
            status=FriendRequest.Status.PENDING,
        ).select_related("from_user", "to_user")


class FriendRequestOutgoingListView(generics.ListAPIView):
    serializer_class = FriendRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FriendRequest.objects.filter(
            from_user=self.request.user,
            status=FriendRequest.Status.PENDING,
        ).select_related("from_user", "to_user")


class FriendRequestAcceptView(APIView):
    """POST /api/social/friends/requests/<uuid>/accept/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        fr = (
            FriendRequest.objects.filter(
                id=request_id,
                to_user=request.user,
                status=FriendRequest.Status.PENDING,
            )
            .select_related("from_user", "to_user")
            .first()
        )
        if not fr:
            return Response({"detail": "Not found"}, status=404)
        add_friendship(fr.from_user, fr.to_user)
        requester = fr.from_user
        accepter = fr.to_user
        fr.status = FriendRequest.Status.ACCEPTED
        fr.save(update_fields=["status"])
        notify_friend_accepted(accepter=accepter, requester=requester)
        return Response({"ok": True})


class FriendRequestDeclineView(APIView):
    """POST /api/social/friends/requests/<uuid>/decline/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        fr = FriendRequest.objects.filter(
            id=request_id,
            to_user=request.user,
            status=FriendRequest.Status.PENDING,
        ).first()
        if not fr:
            return Response({"detail": "Not found"}, status=404)
        fr.status = FriendRequest.Status.DECLINED
        fr.save(update_fields=["status"])
        broadcast_social_user(
            fr.from_user_id,
            {
                "type": "social",
                "action": "friend_request_declined",
                "friend_request_id": str(fr.id),
            },
        )
        return Response({"ok": True})


class FriendRequestCancelView(APIView):
    """POST /api/social/friends/requests/<uuid>/cancel/ — sender only."""

    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        fr = FriendRequest.objects.filter(
            id=request_id,
            from_user=request.user,
            status=FriendRequest.Status.PENDING,
        ).first()
        if not fr:
            return Response({"detail": "Not found"}, status=404)
        fr.status = FriendRequest.Status.CANCELLED
        fr.save(update_fields=["status"])
        broadcast_social_user(
            fr.to_user_id,
            {
                "type": "social",
                "action": "friend_request_cancelled",
                "friend_request_id": str(fr.id),
            },
        )
        return Response({"ok": True})


class RecentOpponentsView(APIView):
    """GET /api/social/opponents/recent/ — distinct human opponents from finished games."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = (
            Game.objects.filter(
                status=Game.Status.FINISHED,
                is_ai_game=False,
                is_local_2p=False,
            )
            .filter(Q(player_one=user) | Q(player_two=user))
            .select_related("player_one", "player_two")
            .order_by("-finished_at")[:80]
        )
        seen: set[int] = set()
        opponents: list[User] = []
        for g in qs:
            if g.player_one_id == user.id:
                other = g.player_two
            else:
                other = g.player_one
            if not other or other.id == user.id:
                continue
            if other.id in seen:
                continue
            seen.add(other.id)
            opponents.append(other)
            if len(opponents) >= 24:
                break
        return Response(PlayerPublicSerializer(opponents, many=True).data)


class VapidPublicKeyView(APIView):
    """GET /api/social/push/vapid-public-key/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.conf import settings as dj_settings

        pub = getattr(dj_settings, "VAPID_PUBLIC_KEY", "") or ""
        if not str(pub).strip():
            return Response(
                {"enabled": False, "public_key": None},
            )
        return Response({"enabled": True, "public_key": pub.strip()})


class PushSubscribeView(APIView):
    """POST /api/social/push/subscribe/ — register Web Push subscription."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = PushSubscribeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        endpoint = ser.validated_data["endpoint"]
        keys = ser.validated_data["keys"]
        p256dh = keys["p256dh"]
        auth = keys["auth"]
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": p256dh,
                "auth": auth,
            },
        )
        return Response({"ok": True})


class PushUnsubscribeView(APIView):
    """POST /api/social/push/unsubscribe/ — { endpoint }"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = PushUnsubscribeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        endpoint = ser.validated_data["endpoint"]
        deleted, _ = PushSubscription.objects.filter(
            user=request.user,
            endpoint=endpoint,
        ).delete()
        return Response({"ok": True, "removed": deleted})


class UnreadNotificationCountView(APIView):
    """GET /api/social/notifications/unread-count/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        n = Notification.objects.filter(
            recipient=request.user,
            read_at__isnull=True,
        ).count()
        return Response({"count": n})


class LinkFacebookView(APIView):
    """POST /api/social/link/facebook/ — { access_token } from Facebook Login."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = LinkFacebookSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        token = ser.validated_data["access_token"]
        me = verify_facebook_token(token)
        if not me or not me.get("id"):
            return Response(
                {"detail": "Invalid or expired Facebook token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        facebook_id = str(me["id"])
        other = User.objects.filter(facebook_id=facebook_id).exclude(pk=request.user.pk).first()
        if other:
            return Response(
                {"detail": "This Facebook account is already linked to another Draught user."},
                status=status.HTTP_409_CONFLICT,
            )
        request.user.facebook_id = facebook_id
        request.user.save(update_fields=["facebook_id"])
        return Response({"ok": True, "facebook_linked": True})


class UnlinkFacebookView(APIView):
    """POST /api/social/unlink/facebook/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.facebook_id = None
        request.user.save(update_fields=["facebook_id"])
        return Response({"ok": True, "facebook_linked": False})


class FacebookFriendSuggestionsView(APIView):
    """
    POST /api/social/suggestions/facebook/
    Body: { access_token } — must match the Facebook account already linked to this user.
    Returns Draught users who are Facebook friends *and* use this app (Meta limitation).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.facebook_id:
            return Response(
                {"detail": "Link your Facebook account first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = FacebookFriendSuggestionsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        token = ser.validated_data["access_token"]
        me = verify_facebook_token(token)
        if not me or not me.get("id"):
            return Response(
                {"detail": "Invalid or expired Facebook token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if str(me["id"]) != str(request.user.facebook_id):
            return Response(
                {"detail": "Facebook session does not match your linked account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        fb_friend_ids = fetch_facebook_friend_ids(token)
        already = _friend_user_ids(request.user)
        qs = (
            User.objects.filter(facebook_id__in=fb_friend_ids)
            .exclude(pk=request.user.pk)
            .exclude(pk__in=already)
            .order_by("username")
        )
        hint = ""
        if not fb_friend_ids:
            hint = (
                "No Facebook friends returned. They must also use this Draught app and grant "
                "friend permissions — see Meta’s `user_friends` / Login documentation."
            )
        return Response(
            {
                "results": PlayerPublicSerializer(qs, many=True).data,
                "hint": hint,
            }
        )


class TikTokOAuthConfigView(APIView):
    """GET /api/social/tiktok/config/ — public client_key + redirect for Login Kit."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        key = (getattr(django_settings, "TIKTOK_CLIENT_KEY", "") or "").strip()
        redirect_uri = (getattr(django_settings, "TIKTOK_REDIRECT_URI", "") or "").strip()
        secret = (getattr(django_settings, "TIKTOK_CLIENT_SECRET", "") or "").strip()
        return Response(
            {
                "configured": bool(key and redirect_uri and secret),
                "client_key": key or None,
                "redirect_uri": redirect_uri or None,
                "authorize_url_template": "https://www.tiktok.com/v2/auth/authorize/",
            }
        )


class LinkTikTokView(APIView):
    """POST /api/social/link/tiktok/ — { code, redirect_uri } after OAuth redirect."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = LinkTikTokSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        code = ser.validated_data["code"]
        redirect_uri = ser.validated_data["redirect_uri"]
        allowed = (getattr(django_settings, "TIKTOK_REDIRECT_URI", "") or "").strip()
        if not allowed:
            return Response(
                {"detail": "TIKTOK_REDIRECT_URI is not configured on the server."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if redirect_uri.rstrip("/") != allowed.rstrip("/"):
            return Response(
                {"detail": "redirect_uri must match TIKTOK_REDIRECT_URI on the server."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload = exchange_tiktok_oauth_code(code, redirect_uri)
        if not payload:
            return Response(
                {"detail": "TikTok token exchange failed. Check TIKTOK_CLIENT_* and redirect URI."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        open_id = extract_tiktok_open_id(payload)
        if not open_id:
            return Response(
                {"detail": "TikTok response did not include open_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        other = User.objects.filter(tiktok_open_id=open_id).exclude(pk=request.user.pk).first()
        if other:
            return Response(
                {"detail": "This TikTok account is already linked to another Draught user."},
                status=status.HTTP_409_CONFLICT,
            )
        request.user.tiktok_open_id = open_id
        request.user.save(update_fields=["tiktok_open_id"])
        return Response({"ok": True, "tiktok_linked": True})


class UnlinkTikTokView(APIView):
    """POST /api/social/unlink/tiktok/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.tiktok_open_id = None
        request.user.save(update_fields=["tiktok_open_id"])
        return Response({"ok": True, "tiktok_linked": False})
