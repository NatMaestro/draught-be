"""
WebSocket auth: JWT from query string `?token=` (same tokens as REST SimpleJWT).

Browsers cannot set custom headers on WebSocket handshakes; session cookies work
only if the client uses Django sessions — this app uses JWT in localStorage.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _user_from_jwt(token: str):
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.tokens import AccessToken

    User = get_user_model()
    try:
        access = AccessToken(token)
        user_id = access["user_id"]
        return User.objects.get(pk=user_id)
    except (TokenError, User.DoesNotExist, KeyError, ValueError):
        return None


class JwtQueryAuthMiddleware:
    """
    Sets ``scope["user"]`` from ``?token=<access>`` or AnonymousUser.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "websocket":
            return await self.inner(scope, receive, send)

        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_list = params.get("token")
        token = token_list[0] if token_list else None

        scope = dict(scope)
        scope["user"] = AnonymousUser()
        if token:
            user = await _user_from_jwt(token)
            if user is not None:
                scope["user"] = user

        return await self.inner(scope, receive, send)
