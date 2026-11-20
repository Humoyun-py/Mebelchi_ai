from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.services import track
from apps.calculations import engine
from apps.calculations.serializers import CabinetInputSerializer
from apps.core.throttles import ExportRateThrottle
from apps.subscriptions.services import enforce_export_limit

from . import builder, exporters

FORMATS = {"glb": ("model/gltf-binary", exporters.to_glb), "gltf": ("model/gltf+json", exporters.to_gltf), "obj": ("text/plain", exporters.to_obj)}


def _build(request):
    s = CabinetInputSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    d = {k: v for k, v in s.validated_data.items() if k not in ("save", "name", "project")}
    color = request.data.get("color")
    if color is not None and not (isinstance(color, str) and len(color) == 7 and color.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in color[1:])):
        raise ValidationError({"color": "Must be a hex colour like #c9a27a."})
    try:
        return builder.build_cabinet(d, color)
    except engine.EngineValidationError as e:
        raise ValidationError(e.errors)


class PreviewView(APIView):
    """Stateless and read-only (nothing is stored), so it is public for the marketing site; anonymous calls are throttled."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        return Response(_build(request))


class ExportView(APIView):
    throttle_classes = [ExportRateThrottle]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request, fmt):
        if fmt not in FORMATS:
            raise ValidationError({"format": "Use glb, gltf or obj."})
        enforce_export_limit(request.user)
        model = _build(request)
        ctype, fn = FORMATS[fmt]
        track(request.user, f"export_{fmt}")
        resp = HttpResponse(fn(model["boxes"]), content_type=ctype)
        resp["Content-Disposition"] = f'attachment; filename="mebelchi-cabinet.{fmt}"'
        return resp
