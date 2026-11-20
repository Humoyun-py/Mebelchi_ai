from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers

from .models import FurnitureTemplate
from .seed_data import CATEGORIES


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FurnitureTemplate
        fields = ["id", "slug", "category", "name", "description", "defaults"]


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FurnitureTemplate.objects.filter(is_active=True)
    serializer_class = TemplateSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["category"]
    search_fields = ["name", "description"]
    pagination_class = None


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
def categories(request):
    return Response(CATEGORIES)
