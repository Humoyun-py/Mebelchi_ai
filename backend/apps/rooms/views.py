from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import RoomFlow
from .serializers import AnswerSerializer, ItemRevSerializer, ItemSerializer, RoomFlowSummarySerializer, parse_rev

OBJ = OpenApiTypes.OBJECT


class RoomFlowViewSet(viewsets.GenericViewSet):
    """The room-design conversation. Every query is scoped to the requesting user; another user's flow is a 404."""

    permission_classes = [IsAuthenticated]
    serializer_class = RoomFlowSummarySerializer
    queryset = RoomFlow.objects.all()
    lookup_value_regex = r"\d+"
    filterset_fields = ["status"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RoomFlow.objects.none()
        return RoomFlow.objects.filter(owner=self.request.user)

    def _flow(self, pk):
        return services.get_flow(self.request.user, pk)

    @extend_schema(responses=RoomFlowSummarySerializer(many=True))
    def list(self, request):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @extend_schema(request=None, responses=OBJ)
    def create(self, request):
        return Response(services.view(services.start(request.user)), status=status.HTTP_201_CREATED)

    @extend_schema(responses=OBJ)
    def retrieve(self, request, pk=None):
        return Response(services.view(self._flow(pk)))

    @extend_schema(request=AnswerSerializer, responses=OBJ)
    @action(detail=True, methods=["post"])
    def answer(self, request, pk=None):
        s = AnswerSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(services.answer(self._flow(pk), s.validated_data["step"], s.validated_data["value"]))

    @extend_schema(request=None, responses=OBJ)
    @action(detail=True, methods=["post"])
    def back(self, request, pk=None):
        return Response(services.back(self._flow(pk)))

    @extend_schema(request=None, responses=OBJ)
    @action(detail=True, methods=["post"])
    def abandon(self, request, pk=None):
        return Response(services.abandon(self._flow(pk)))

    @extend_schema(responses=OBJ)
    @action(detail=True, methods=["get"])
    def model(self, request, pk=None):
        return Response(services.model(self._flow(pk)))

    @extend_schema(request=ItemSerializer, responses={201: OBJ})
    @action(detail=True, methods=["post"], url_path="items")
    def items(self, request, pk=None):
        s = ItemSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        rev = parse_rev(request, data.pop("rev", None))
        return Response(services.add_item(self._flow(pk), data, rev), status=status.HTTP_201_CREATED)

    @extend_schema(request=ItemSerializer, responses=OBJ)
    @action(detail=True, methods=["patch"], url_path=r"items/(?P<item_id>[0-9a-f]{12})")
    def item_update(self, request, pk=None, item_id=None):
        s = ItemSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        rev = parse_rev(request, data.pop("rev", None))
        return Response(services.update_item(self._flow(pk), item_id, data, rev))

    @extend_schema(request=ItemRevSerializer, responses=OBJ)
    @item_update.mapping.delete
    def item_delete(self, request, pk=None, item_id=None):
        s = ItemRevSerializer(data={**request.query_params.dict(), **(request.data if isinstance(request.data, dict) else {})})
        s.is_valid(raise_exception=True)
        return Response(services.delete_item(self._flow(pk), item_id, parse_rev(request, s.validated_data.get("rev"))))
