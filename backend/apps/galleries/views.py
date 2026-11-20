from django.http import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.signing import verify_file
from apps.core.views import OwnedModelViewSet
from apps.subscriptions.services import enforce_storage_limit

from .models import GalleryImage
from .serializers import GalleryImageSerializer


class GalleryViewSet(OwnedModelViewSet):
    queryset = GalleryImage.objects.all()
    serializer_class = GalleryImageSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["favorite", "source", "project"]
    search_fields = ["name"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer):
        enforce_storage_limit(self.request.user, serializer.validated_data["image"].size)
        super().perform_create(serializer)

    def perform_destroy(self, instance):
        instance.image.delete(save=False)
        instance.delete()

    @action(detail=True, methods=["post"])
    def favorite(self, request, pk=None):
        obj = self.get_object()
        obj.favorite = not obj.favorite
        obj.save(update_fields=["favorite"])
        return Response(self.get_serializer(obj).data)


class GalleryFileView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes: list = []  # cheap/static or signature-protected: the anonymous per-IP limit would break shared networks

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def get(self, request, pk):
        if not verify_file(request.query_params.get("sig", ""), "image", pk):
            raise Http404
        obj = GalleryImage.objects.filter(pk=pk).first()
        if not obj:
            raise Http404
        dl = request.query_params.get("download") == "1"
        return FileResponse(obj.image.open("rb"), as_attachment=dl, filename=obj.name + "." + obj.image.name.rsplit(".", 1)[-1])
