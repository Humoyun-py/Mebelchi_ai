from datetime import date

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsPlatformAdmin
from apps.workshops.models import Order

from . import services
from .models import OrderPayment


class PaymentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)

    class Meta:
        model = OrderPayment
        fields = ["id", "order", "order_number", "kind", "status", "method", "amount", "reference", "note", "reject_reason", "created_at", "decided_at"]
        read_only_fields = fields


class PaymentInput(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    method = serializers.ChoiceField(choices=OrderPayment.Method.choices, default="other")
    reference = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(max_length=64, required=False, allow_null=True, default=None)


class AdminPaymentInput(PaymentInput):
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    kind = serializers.ChoiceField(choices=OrderPayment.Kind.choices, default="payment")
    confirm = serializers.BooleanField(default=True, help_text="Record and confirm in one step (the money was received by the administrator)")


class PaymentViewSet(viewsets.GenericViewSet):
    """Administrators: every payment, manual recording, confirmation and rejection."""

    permission_classes = [IsPlatformAdmin]
    serializer_class = PaymentSerializer
    filterset_fields = ["status", "kind", "order", "order__workshop"]
    ordering_fields = ["created_at", "amount"]

    def get_queryset(self):
        return OrderPayment.objects.select_related("order")

    def list(self, request):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        return self.get_paginated_response(PaymentSerializer(page, many=True).data)

    @extend_schema(request=AdminPaymentInput, responses=PaymentSerializer)
    def create(self, request):
        s = AdminPaymentInput(data=request.data)
        s.is_valid(raise_exception=True)
        d = dict(s.validated_data)
        order, confirm = d.pop("order"), d.pop("confirm")
        row, created = services.create_payment(request.user, order, **d)
        if confirm and row.status == OrderPayment.Status.PENDING:
            row = services.confirm_payment(request.user, row.pk)
        return Response(PaymentSerializer(row).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(request=None, responses=PaymentSerializer)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        get_object_or_404(self.get_queryset(), pk=pk)
        return Response(PaymentSerializer(services.confirm_payment(request.user, int(pk))).data)

    @extend_schema(request=OpenApiTypes.OBJECT, responses=PaymentSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        get_object_or_404(self.get_queryset(), pk=pk)
        reason = request.data.get("reason", "") if isinstance(request.data, dict) else ""
        return Response(PaymentSerializer(services.reject_payment(request.user, int(pk), str(reason))).data)


class CommissionView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        s = services.PlatformSettings.get()
        return Response({"commission_percent": s.commission_percent, "updated_at": s.updated_at})

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def patch(self, request):
        """Body `{"commission_percent": 20}`. New orders use the new rate; orders already placed keep the rate they were placed with."""
        if not isinstance(request.data, dict) or "commission_percent" not in request.data:
            raise ValidationError({"commission_percent": "is required"})
        s = services.set_commission_percent(request.user, request.data["commission_percent"])
        return Response({"commission_percent": s.commission_percent, "updated_at": s.updated_at})


class SummaryView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        def d(k):
            v = request.query_params.get(k)
            try:
                return date.fromisoformat(v) if v else None
            except ValueError:
                raise ValidationError({k: "use YYYY-MM-DD"})
        ws = request.query_params.get("workshop")
        if ws and not ws.isdigit():
            raise ValidationError({"workshop": "must be a workshop id"})
        return Response(services.summary(date_from=d("from"), date_to=d("to"), workshop_id=int(ws) if ws else None))
