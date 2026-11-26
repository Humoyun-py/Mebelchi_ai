from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance import services as finance
from apps.finance.views import PaymentInput, PaymentSerializer
from apps.workshops.models import Order

from . import matching, services

ACCEPTED = {Order.Status.CONFIRMED, Order.Status.IN_PRODUCTION, Order.Status.QUALITY_CHECK, Order.Status.READY, Order.Status.DELIVERY, Order.Status.DELIVERED}


def present(o: Order, *, detail=False) -> dict:
    """What a customer may see of their own order: the workshop's public face, price, progress and payments. Never the workshop's employees,
    internal tasks, or the commission split."""
    ws = o.workshop
    q = o.quote or {}
    can_pay = o.status in (Order.Status.CONFIRMED, Order.Status.IN_PRODUCTION, Order.Status.QUALITY_CHECK, Order.Status.READY, Order.Status.DELIVERY) \
        and o.payment_status in (Order.PaymentStatus.UNPAID, Order.PaymentStatus.PARTIALLY_PAID)
    review = getattr(o, "review", None) if o.status == Order.Status.DELIVERED else None
    out = {"id": o.pk, "order_number": o.order_number, "status": o.status, "title": o.title, "total_price": str(o.total_price), "currency": q.get("currency"),
           "paid_amount": str(o.paid_amount), "payment_status": o.payment_status, "price_tier": o.price_tier, "deadline": o.deadline, "created_at": o.created_at,
           "updated_at": o.updated_at, "responded_at": o.responded_at, "rejection_reason": o.rejection_reason, "rerouted_from": o.rerouted_from_id,
           "workshop": {"id": ws.pk, "name": ws.name, "city": ws.city, "rating": float(ws.rating_avg) if ws.rating_count else None, "rating_count": ws.rating_count,
                        "phone": (ws.phone or None) if o.status in ACCEPTED else None},
           "actions": {"cancel": o.status in (Order.Status.PENDING, Order.Status.CONFIRMED) and o.paid_amount == 0,
                       "pay": can_pay, "reassign": o.status == Order.Status.REJECTED and not o.rerouted_to.exists(),
                       "review": o.status == Order.Status.DELIVERED and review is None},
           "review": {"stars": review.stars, "comment": review.comment} if review else None}
    if detail:
        out.update({"quantity": q.get("quantity"), "lines": q.get("lines", []), "notes": q.get("notes", []), "description": o.description,
                    "customer_address": o.customer_address, "delivery_distance_km": o.delivery_distance_km,
                    "payments": PaymentSerializer(o.payments.all(), many=True).data,
                    "history": [{"from": h.from_status, "to": h.to_status, "at": h.created_at, "note": h.note} for h in o.status_history.all()]})
    return out


class MatchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        """Best workshops for a piece of furniture. Creates nothing and contacts nobody.

        Body: `catalog_item` (id) or `furniture` {category, width, height, depth, thickness?, shelves?, doors?, drawers?}; optional `quantity`,
        `customer_location` {latitude, longitude}, `budget`, `deadline_days`, `currency`, `limit` (1-10, default 3), `exclude_workshops`.
        Response: `options` (ranked, each with price, tier, distance, rating, lead time, load, score breakdown, portfolio), `tiers`
        {min, average, premium} over all quotes received, and `excluded` with the reason for every workshop that was left out."""
        return Response(services.find_matches(request.user, request.data))


class CustomerOrderViewSet(viewsets.GenericViewSet):
    """The signed-in customer's marketplace orders. Placing one is what sends it to the workshop."""

    permission_classes = [IsAuthenticated]
    filterset_fields = ["status"]
    ordering_fields = ["created_at", "updated_at"]

    def get_queryset(self):
        return services.my_orders(self.request.user)

    def get_serializer_class(self):
        from rest_framework import serializers
        return serializers.Serializer

    def list(self, request):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        return self.get_paginated_response([present(o) for o in page])

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def create(self, request):
        """Body: the same furniture fields as `match/` plus `workshop` (one of the offered ids), optional `customer_name`, `customer_phone`,
        `customer_address`, `notes`. The price is recomputed on the server; the order starts as `pending` and the workshop has 24 hours to answer."""
        o = services.place_order(request.user, request.data)
        return Response(present(services.get_order(request.user, o.pk), detail=True), status=status.HTTP_201_CREATED)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def retrieve(self, request, pk=None):
        return Response(present(services.get_order(request.user, pk), detail=True))

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        services.cancel(request.user, pk)
        return Response(present(services.get_order(request.user, pk), detail=True))

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"])
    def alternatives(self, request, pk=None):
        """Other workshops for a rejected order (the ones that already refused are never offered)."""
        return Response(services.alternatives(request.user, pk))

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    def reassign(self, request, pk=None):
        """Body `{"workshop": id}`: sends a rejected order to another workshop as a new pending order."""
        ws = request.data.get("workshop") if isinstance(request.data, dict) else None
        if isinstance(ws, bool) or not isinstance(ws, int):
            raise ValidationError({"workshop": "choose a workshop id"})
        o = services.reassign(request.user, pk, ws)
        return Response(present(services.get_order(request.user, o.pk), detail=True), status=status.HTTP_201_CREATED)

    @extend_schema(request=PaymentInput, responses=PaymentSerializer)
    @action(detail=True, methods=["post"])
    def payments(self, request, pk=None):
        """Tell the platform you paid (amount, method, receipt number). It counts only after an administrator confirms it. Send an
        `idempotency_key` so a retry never records the payment twice."""
        o = services.get_order(request.user, pk)
        s = PaymentInput(data=request.data)
        s.is_valid(raise_exception=True)
        row, created = finance.create_payment(request.user, o, kind="payment", **s.validated_data)
        return Response(PaymentSerializer(row).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """Body `{"stars": 1-5, "comment": ""}` once the order is completed; one rating per order."""
        d = request.data if isinstance(request.data, dict) else {}
        r = services.review(request.user, pk, d.get("stars"), d.get("comment", ""))
        return Response({"stars": r.stars, "comment": r.comment}, status=status.HTTP_201_CREATED)
