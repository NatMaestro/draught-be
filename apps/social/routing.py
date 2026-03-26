"""WebSocket routes for social realtime."""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/social/$", consumers.UserSocialConsumer.as_asgi()),
]
