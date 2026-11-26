from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound as DRFNotFound
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.conversations import flow
from apps.geometry import room as geo

from . import services
from .models import RoomFlow


def _fields(errors: dict) -> ValidationError:
    return ValidationError({k: [v] if isinstance(v, str) else v for k, v in errors.items()})


def guarded(fn):
    """Turns the service-layer exceptions into the API's error envelope: 400 bad value, 404 not yours / not there, 409 wrong state."""
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except services.NotFound:
            raise DRFNotFound()
        except flow.StepMismatch as e:
            return Response({"error": {"status": 409, "detail": str(e), "expected_step": e.expected}}, status=status.HTTP_409_CONFLICT)
        except flow.FlowValidationError as e:
            raise _fields(e.errors)
        except flow.FlowError as e:
            return Response({"error": {"status": 409, "detail": str(e)}}, status=status.HTTP_409_CONFLICT)
        except geo.RoomError as e:
            raise _fields(e.errors)
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def payload(f: RoomFlow, **extra) -> dict:
    ctx = services.context()
    return {"id": f.pk, "status": f.status, "step": f.step, "answers": f.answers, "question": flow.describe(services.state_of(f), ctx),
            "design": f.design_id, "room": services.room_view(f), "created_at": f.created_at, "updated_at": f.updated_at, **extra}


def brief(f: RoomFlow) -> dict:
    return {"id": f.pk, "status": f.status, "step": f.step, "goal": (f.answers or {}).get("goal"), "design": f.design_id, "created_at": f.created_at, "updated_at": f.updated_at}


class RoomFlowViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Room design conversation (goal -> photo -> elements -> size -> openings -> style -> furnish -> done) and the furniture in the room.
    Every route is scoped to the signed-in user: a flow that is not yours answers 404."""

    permission_classes = [IsAuthenticated]
    filterset_fields = ["status"]
    ordering_fields = ["updated_at", "created_at"]

    def get_queryset(self):
        return RoomFlow.objects.filter(owner=self.request.user)

    def get_serializer_class(self):  # schema only; responses are built by hand
        from rest_framework import serializers
        return serializers.Serializer

    def list(self, request, *a, **kw):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        return self.get_paginated_response([brief(f) for f in page])

    def _flow(self, request, pk) -> RoomFlow:
        f = self.get_queryset().select_related("design").filter(pk=pk).first()
        if f is None:
            raise DRFNotFound()
        return f

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    @guarded
    def create(self, request):
        return Response(payload(services.start(request.user)), status=status.HTTP_201_CREATED)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def retrieve(self, request, pk=None):
        return Response(payload(self._flow(request, pk)))

    @extend_schema(responses={204: None})
    @guarded
    def destroy(self, request, pk=None):
        services.delete(request.user, self._flow(request, pk).pk)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    @guarded
    def answer(self, request, pk=None):
        """Body `{"step": "<current step>", "value": ...}`. 409 when `step` is not the current step."""
        self._flow(request, pk)
        step = request.data.get("step") if isinstance(request.data, dict) else None
        if not isinstance(step, str) or "value" not in request.data:
            raise ValidationError({"step": ["send {\"step\": ..., \"value\": ...}"]})
        return Response(payload(services.answer(request.user, int(pk), step, request.data["value"])))

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    @guarded
    def back(self, request, pk=None):
        self._flow(request, pk)
        return Response(payload(services.back(request.user, int(pk))))

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    @guarded
    def finish(self, request, pk=None):
        self._flow(request, pk)
        return Response(payload(services.finish(request.user, int(pk))))

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"])
    @guarded
    def model(self, request, pk=None):
        """Boxes for the 3D viewer (walls, floor, ceiling, furniture), rebuilt from the saved config."""
        return Response(services.model(self._flow(request, pk)))

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"], url_path="reset-layout")
    @guarded
    def reset_layout(self, request, pk=None):
        self._flow(request, pk)
        return Response(payload(services.reset_layout(request.user, int(pk))))

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"], url_path="items")
    @guarded
    def add_item(self, request, pk=None):
        """`{"template": slug, x?, z?, rot?, width?, depth?, height?, shelves?, doors?, drawers?, color?, name?}`; without x and z the item is placed automatically."""
        self._flow(request, pk)
        f, item, warnings = services.add_item(request.user, int(pk), request.data)
        return Response(payload(f, item=item, item_warnings=warnings), status=status.HTTP_201_CREATED)

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["patch", "delete"], url_path=r"items/(?P<item_id>[0-9a-zA-Z_-]{1,64})")
    @guarded
    def item(self, request, pk=None, item_id=None):
        self._flow(request, pk)
        if request.method == "DELETE":
            return Response(payload(services.remove_item(request.user, int(pk), item_id)))
        f, item, warnings = services.update_item(request.user, int(pk), item_id, request.data)
        return Response(payload(f, item=item, item_warnings=warnings))
