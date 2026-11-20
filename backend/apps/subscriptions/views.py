from rest_framework import serializers
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Payment, Plan


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["slug", "name", "price_usd", "storage_mb", "max_projects", "max_exports_per_month", "features"]


class PlanListView(ListAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes: list = []  # cheap/static or signature-protected: the anonymous per-IP limit would break shared networks
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    pagination_class = None


class MySubscriptionView(APIView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        data = services.usage(request.user)
        data["payments"] = [{"id": p.id, "plan": p.plan.name, "amount": str(p.amount), "status": p.status, "created_at": p.created_at}
                            for p in Payment.objects.filter(user=request.user).select_related("plan")[:20]]
        return Response(data)


class UpgradeSerializer(serializers.Serializer):
    plan = serializers.SlugField()


class UpgradeView(APIView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        s = UpgradeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        plan = Plan.objects.filter(slug=s.validated_data["plan"], is_active=True).first()
        if not plan:
            raise NotFound("Plan not found.")
        return Response(services.request_upgrade(request.user, plan))
