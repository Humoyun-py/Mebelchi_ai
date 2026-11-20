from django.http import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.core.signing import verify_file
from apps.core.views import OwnedModelViewSet
from apps.subscriptions.services import enforce_storage_limit

from .models import UserFile
from .serializers import UserFileSerializer


class UserFileViewSet(OwnedModelViewSet):
    queryset = UserFile.objects.all()
    serializer_class = UserFileSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["kind", "project"]
    search_fields = ["name"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer):
        enforce_storage_limit(self.request.user, serializer.validated_data["file"].size)
        super().perform_create(serializer)

    def perform_destroy(self, instance):
        instance.file.delete(save=False)
        instance.delete()


class FileDownloadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes: list = []  # cheap/static or signature-protected: the anonymous per-IP limit would break shared networks

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def get(self, request, pk):
        if not verify_file(request.query_params.get("sig", ""), "file", pk):
            raise Http404
        obj = UserFile.objects.filter(pk=pk).first()
        if not obj:
            raise Http404
        return FileResponse(obj.file.open("rb"), as_attachment=True, filename=obj.name)
