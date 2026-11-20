from apps.core.views import OwnedModelViewSet

from .models import Design
from .serializers import DesignSerializer


class DesignViewSet(OwnedModelViewSet):
    queryset = Design.objects.all()
    serializer_class = DesignSerializer
    filterset_fields = ["kind", "project"]
    search_fields = ["name"]
