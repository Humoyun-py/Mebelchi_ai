from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from . import providers


class AIStatusView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        """Whether an AI provider is configured. Clients hide AI-only features when `enabled` is false."""
        return Response(providers.status())
