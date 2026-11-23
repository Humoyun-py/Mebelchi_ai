"""Telegram bot endpoints for the room-design flow. Same use cases as the web API (services.py); the bot authenticates
with X-Bot-Secret and acts for the account linked to `telegram_id`. A Telegram ID that is not linked is a 404, and a flow
that belongs to another account is a 404 too."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.integrations.views import BotView

from . import services
from .serializers import (BotAnswerSerializer, BotItemSerializer, BotPhotoSerializer, BotStartSerializer, BotTelegramSerializer, ItemRevSerializer,
                          parse_rev)

OBJ = OpenApiTypes.OBJECT


class BotRoomFlowView(BotView):
    def flow(self, request, pk, source):
        return services.get_flow(self.user_for(self.telegram_id_from(source)), pk)


class BotRoomFlowStartView(BotView):
    @extend_schema(request=BotStartSerializer, responses=OBJ)
    def post(self, request):
        s = BotStartSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = self.user_for(s.validated_data["telegram_id"])
        flow, created = services.start_or_resume(user, s.validated_data["new"])
        return Response(services.view(flow), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class BotRoomFlowDetailView(BotRoomFlowView):
    @extend_schema(request=None, responses=OBJ)
    def get(self, request, pk):
        return Response(services.view(self.flow(request, pk, request.query_params)))


class BotRoomFlowAnswerView(BotRoomFlowView):
    @extend_schema(request=BotAnswerSerializer, responses=OBJ)
    def post(self, request, pk):
        s = BotAnswerSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        flow = services.get_flow(self.user_for(s.validated_data["telegram_id"]), pk)
        return Response(services.answer(flow, s.validated_data["step"], s.validated_data["value"]))


class BotRoomFlowBackView(BotRoomFlowView):
    @extend_schema(request=BotTelegramSerializer, responses=OBJ)
    def post(self, request, pk):
        return Response(services.back(self.flow(request, pk, request.data)))


class BotRoomFlowAbandonView(BotRoomFlowView):
    @extend_schema(request=BotTelegramSerializer, responses=OBJ)
    def post(self, request, pk):
        return Response(services.abandon(self.flow(request, pk, request.data)))


class BotRoomFlowModelView(BotRoomFlowView):
    @extend_schema(request=None, responses=OBJ)
    def get(self, request, pk):
        return Response(services.model(self.flow(request, pk, request.query_params)))


class BotRoomFlowPhotoView(BotRoomFlowView):
    @extend_schema(request=BotPhotoSerializer, responses=OBJ)
    def post(self, request, pk):
        s = BotPhotoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        flow = services.get_flow(self.user_for(s.validated_data["telegram_id"]), pk)
        return Response(services.attach_photo(flow, s.validated_data["file"]), status=status.HTTP_201_CREATED)


class BotRoomFlowItemsView(BotRoomFlowView):
    @extend_schema(request=BotItemSerializer, responses={201: OBJ})
    def post(self, request, pk):
        s = BotItemSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        flow = services.get_flow(self.user_for(data.pop("telegram_id")), pk)
        rev = parse_rev(request, data.pop("rev", None))
        return Response(services.add_item(flow, data, rev), status=status.HTTP_201_CREATED)


class BotRoomFlowItemDetailView(BotRoomFlowView):
    @extend_schema(request=BotItemSerializer, responses=OBJ)
    def patch(self, request, pk, item_id):
        user = self.user_for(self.telegram_id_from(request.data))   # partial updates: telegram_id is still mandatory
        s = BotItemSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        data.pop("telegram_id", None)
        flow = services.get_flow(user, pk)
        rev = parse_rev(request, data.pop("rev", None))
        return Response(services.update_item(flow, item_id, data, rev))

    @extend_schema(request=None, responses=OBJ, parameters=[ItemRevSerializer])
    def delete(self, request, pk, item_id):
        flow = self.flow(request, pk, request.query_params)
        s = ItemRevSerializer(data=request.query_params.dict())
        s.is_valid(raise_exception=True)
        return Response(services.delete_item(flow, item_id, parse_rev(request, s.validated_data.get("rev"))))
