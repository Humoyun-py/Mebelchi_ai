from rest_framework.response import Response
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.core.views import OwnedModelViewSet

from .models import Folder
from .serializers import FolderSerializer


class FolderViewSet(OwnedModelViewSet):
    queryset = Folder.objects.all()
    serializer_class = FolderSerializer
    search_fields = ["name"]
    pagination_class = None


class WorkspaceSummaryView(APIView):
    """Counts powering the sidebar and dashboard cards."""

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        u = request.user
        from apps.projects.models import Project
        projects = Project.objects.filter(owner=u)
        return Response({
            "projects": projects.filter(status="active").count(),
            "archived": projects.filter(status="archived").count(),
            "pinned": projects.filter(pinned=True, status="active").count(),
            "folders": u.folders.count(),
            "calculations": u.calculations.count(),
            "cutting_lists": u.cutting_lists.count(),
            "designs": u.designs.count(),
            "images": u.gallery_images.count(),
            "files": u.files.count(),
            "conversations": u.conversations.count(),
            "models_3d": u.files.filter(kind="model").count(),
        })
