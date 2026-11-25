"""Per-request context (who is calling, from where). Set by the middleware, read when a model change is recorded."""
from contextvars import ContextVar

from django.conf import settings

_current: ContextVar[dict | None] = ContextVar("audit_request", default=None)


def client_ip(request) -> str | None:
    """Uses AUDIT_IP_HEADER (default REMOTE_ADDR). Only set it to a proxy header (e.g. HTTP_X_REAL_IP) when every request really
    passes through that proxy, otherwise clients could forge it."""
    header = getattr(settings, "AUDIT_IP_HEADER", "REMOTE_ADDR")
    value = request.META.get(header) or request.META.get("REMOTE_ADDR")
    if value and "," in value:
        value = value.split(",")[0].strip()
    return value or None


def set_request(request):
    return _current.set({"request": request})


def reset(token):
    _current.reset(token)


def get_context() -> dict:
    """{actor, ip, method, path} of the active request, or {} outside a request (Celery, shell, migrations)."""
    ctx = _current.get()
    if not ctx:
        return {}
    request = ctx["request"]
    # DRF copies the authenticated user onto the Django request, so JWT calls resolve here too.
    user = getattr(request, "user", None)
    actor = user if user is not None and getattr(user, "is_authenticated", False) else None
    return {"actor": actor, "ip": client_ip(request), "method": request.method[:8], "path": request.path[:255]}
