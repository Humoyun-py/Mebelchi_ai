from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound as DRFNotFound
from rest_framework.exceptions import ValidationError
from django.http import HttpResponse
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.conversations import flow
from apps.geometry import room as geo

from . import legacy, mebelchi, services
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
        except (geo.RoomError, legacy.LegacyError, mebelchi.MebelchiError) as e:
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

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=["post"], url_path="import-design")
    @guarded
    def import_design(self, request):
        """Body `{"design": <id>}`: opens an old interior design in the room designer (201 first time, 200 when it was imported before).
        The old design is kept unchanged; the room designer works on a copy. 400 names the old field that cannot be converted."""
        d = request.data.get("design") if isinstance(request.data, dict) else None
        if isinstance(d, bool) or not isinstance(d, int):
            raise ValidationError({"design": ["send {\"design\": <design id>}"]})
        f, created = services.import_legacy(request.user, d)
        return Response(payload(f, imported=True), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(request={"multipart/form-data": OpenApiTypes.OBJECT}, responses=OpenApiTypes.OBJECT)
    @action(detail=False, methods=["post"], url_path="import", parser_classes=[MultiPartParser, FormParser, JSONParser])
    @guarded
    def import_project(self, request):
        """Creates a new room design from a `.mebelchi` project file (multipart field `file`, or the document itself as JSON).
        400 names the place in the file that is wrong; `unknown_models` lists catalogue ids this server does not have."""
        up = request.FILES.get("file") if hasattr(request, "FILES") else None
        raw = up.read() if up is not None else request.data
        if up is None and not (isinstance(raw, dict) and raw):
            raise ValidationError({"file": ["send the .mebelchi file as `file`"]})
        f, unknown = services.import_project(request.user, raw)
        return Response(payload(f, unknown_models=unknown), status=status.HTTP_201_CREATED)

    @extend_schema(responses=OpenApiTypes.BINARY)
    @action(detail=True, methods=["get"], url_path="export")
    @guarded
    def export_project(self, request, pk=None):
        """The design as a `.mebelchi` project file (readable on web and mobile). Not copy protection: see docs/API.md."""
        from apps.rooms import mebelchi
        name, doc = services.export_project(request.user, int(pk))
        safe = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in name).strip() or "room"
        return HttpResponse(mebelchi.dumps(doc), content_type="application/vnd.mebelchi+json",
                            headers={"Content-Disposition": f'attachment; filename="{safe}{mebelchi.EXTENSION}"'})

    @extend_schema(responses=OpenApiTypes.BINARY)
    @action(detail=True, methods=["get"], url_path="export-glb")
    @guarded
    def export_glb(self, request, pk=None):
        """The 3D room as a standard GLB for other viewers (boxes with colours, no textures). `?cutaway=1` drops the ceiling and the two front walls
        (what the in-app viewers show); the default export is the complete room."""
        name, data = services.export_glb(request.user, int(pk), cut=request.query_params.get("cutaway") in ("1", "true"))
        return HttpResponse(data, content_type="model/gltf-binary", headers={"Content-Disposition": 'attachment; filename="room.glb"'})

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["patch"], url_path="settings")
    @guarded
    def room_settings(self, request, pk=None):
        """Wall/floor colour, `floor_material`, `light` {intensity, warm} and `camera` {position, target, fov} of the 3D room."""
        self._flow(request, pk)
        return Response(payload(services.update_settings(request.user, int(pk), request.data)))

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
