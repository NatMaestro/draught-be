"""Minimal URL handlers for non–API routes (root, probes)."""

from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse


def root(request):
    """GET|HEAD / — avoids 404 for health checks (GET/HEAD) and browser hits to the host root."""
    if request.method == "HEAD":
        return HttpResponse()
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET", "HEAD"])
    return JsonResponse(
        {
            "service": "Draught API",
            "docs": "/api/docs/",
            "schema": "/api/schema/",
            "admin": "/admin/",
        }
    )
