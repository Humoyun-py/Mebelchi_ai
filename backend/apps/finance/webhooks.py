"""Public webhook endpoint for payment providers: POST /api/v1/payments/webhook/<provider>/

A plain Django view on purpose: providers send their own content types (Payme uses `text/json`), no JWT, no cookies. Authenticity is the
provider's own scheme, checked inside the provider class; this view only routes. Unknown provider -> 404, provider not implemented or not
configured -> 503 and nothing is read or recorded."""
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .providers import get_provider


@csrf_exempt
def webhook(request, provider: str):
    p = get_provider(provider)
    if p is None:
        return JsonResponse({"detail": "Unknown payment provider."}, status=404)
    if not p.implemented or not p.enabled:
        return JsonResponse({"detail": f"{p.name} payments are not configured on this server."}, status=503)
    status, body = p.handle_webhook(method=request.method, body=request.body, headers={"Authorization": request.headers.get("Authorization", "")})
    return JsonResponse(body, status=status)
