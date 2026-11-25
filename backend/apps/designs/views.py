from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.calculations import engine
from apps.core.views import OwnedModelViewSet

from . import furniture

from .models import Design
from .serializers import DesignSerializer


class DesignViewSet(OwnedModelViewSet):
    queryset = Design.objects.all()
    serializer_class = DesignSerializer
    filterset_fields = ["kind", "project"]
    search_fields = ["name"]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"])
    def model(self, request, pk=None):
        """The 3D model and the calculation, rebuilt from the saved config (never from stale stored numbers)."""
        d = self.get_object()
        if d.kind != Design.Kind.FURNITURE or "input" not in d.config:
            raise ValidationError({"detail": "This design has no furniture model to rebuild."})
        try:
            return Response({"design": d.pk, "name": d.name, "config": d.config, **furniture.rebuild(d.config)})
        except (engine.EngineValidationError, ValueError) as e:
            detail = "; ".join(f"{k}: {v}" for k, v in e.errors.items()) if hasattr(e, "errors") else str(e)
            raise ValidationError({"detail": f"This design no longer passes validation ({detail}). Open it in the editor and adjust it."})

    @extend_schema(request=None, responses=DesignSerializer)
    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        src = self.get_object()
        with transaction.atomic():
            copy = Design.objects.create(owner=request.user, project=src.project, kind=src.kind, name=f"{src.name[:150]} (copy)", config=src.config,
                                         room_image=src.room_image)
        return Response(self.get_serializer(copy).data, status=201)
