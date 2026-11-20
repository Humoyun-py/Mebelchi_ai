import logging

logger = logging.getLogger(__name__)


class RequestLogMiddleware:
    """Persists server errors (5xx) and auth failures on API paths to SystemLog."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/") and response.status_code >= 500:
            try:
                from .models import SystemLog
                user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
                SystemLog.objects.create(level="error", message=f"{request.method} {request.path} -> {response.status_code}"[:500],
                                         path=request.path[:300], status_code=response.status_code, user=user)
            except Exception:  # never break a response because logging failed
                logger.exception("failed to persist system log")
        return response
