"""
Middleware: disable CSRF for /api/ so JWT and Swagger work without CSRF token.
"""


class DisableCSRFForAPIMiddleware:
    """
    Set _dont_enforce_csrf_checks for requests to /api/ so JWT auth and Swagger
    work without sending a CSRF token. Admin and other session views still use CSRF.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            setattr(request, "_dont_enforce_csrf_checks", True)
        return self.get_response(request)
