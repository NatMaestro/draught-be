"""
ASGI config for Draught backend - WebSocket support.
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django_asgi_app = get_asgi_application()

from apps.games import routing as games_routing
from apps.games.middleware import JwtQueryAuthMiddleware
from apps.social import routing as social_routing

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JwtQueryAuthMiddleware(
            URLRouter(
                games_routing.websocket_urlpatterns
                + social_routing.websocket_urlpatterns
            ),
        ),
    }
)
