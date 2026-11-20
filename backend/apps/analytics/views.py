from django.db.models import Count
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FeatureFlag, UsageEvent


class MyAnalyticsView(APIView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        ev = UsageEvent.objects.filter(user=request.user).values("kind").annotate(n=Count("id")).order_by("-n")
        return Response({"events": list(ev), "total": sum(e["n"] for e in ev)})


class FeaturesView(APIView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response({f.key: f.enabled for f in FeatureFlag.objects.all()})
