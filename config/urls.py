"""
URL configuration for Draught backend.
"""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.views import root

admin.site.site_header = "Draught Admin"
admin.site.site_title = "Draught"
admin.site.index_title = "Dashboard"

urlpatterns = [
    path("", root, name="root"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/auth/", include("apps.authentication.urls")),
    path("api/users/", include("apps.users.urls")),
    path("api/matchmaking/", include("apps.matchmaking.urls")),
    path("api/games/", include("apps.games.urls")),
    path("api/social/", include("apps.social.urls")),
]
