from django.http import FileResponse, Http404, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.signing import sign_file, verify_file
from apps.core.validators import validate_image
from apps.geometry import builder, exporters
from apps.workshops.models import Workshop

from . import glb, services
from .models import FurnitureImage, FurnitureTemplate
from .seed_data import CATEGORIES

IMAGE_KIND = "catalog-image"
MODEL_KIND = "catalog-model"


class ImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = FurnitureImage
        fields = ["view", "url"]

    def get_url(self, obj) -> str:
        return f"/api/v1/furniture/images/{obj.pk}/file/?sig={sign_file(IMAGE_KIND, obj.pk)}"


class TemplateSerializer(serializers.ModelSerializer):
    """Read: the catalogue entry. Write: either `defaults` or the loose size fields (`width`, `height`, `depth`, ...)."""

    workshop = serializers.PrimaryKeyRelatedField(queryset=Workshop.objects.all(), required=False, allow_null=True)
    workshop_name = serializers.CharField(source="workshop.name", read_only=True, default=None)
    defaults = serializers.JSONField(required=False)
    width = serializers.FloatField(write_only=True, required=False)
    height = serializers.FloatField(write_only=True, required=False)
    depth = serializers.FloatField(write_only=True, required=False)
    thickness = serializers.FloatField(write_only=True, required=False)
    shelves = serializers.IntegerField(write_only=True, required=False)
    doors = serializers.IntegerField(write_only=True, required=False)
    drawers = serializers.IntegerField(write_only=True, required=False)
    images = ImageSerializer(many=True, read_only=True)
    has_model = serializers.SerializerMethodField()
    model_source = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = FurnitureTemplate
        fields = ["id", "slug", "category", "name", "description", "defaults", "width", "height", "depth", "thickness", "shelves", "doors", "drawers",
                  "workshop", "workshop_name", "price", "currency", "material", "color", "manufacturer", "lead_time_days", "is_available",
                  "status", "review_note", "images", "has_model", "model_source", "can_edit", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "status", "review_note", "created_at", "updated_at"]

    def get_has_model(self, obj) -> bool:
        return True                                         # uploaded GLB, or generated from the sizes

    def get_model_source(self, obj) -> str:
        return "uploaded" if obj.glb_file else "parametric"

    def get_can_edit(self, obj) -> bool:
        return services.can_manage(self.context["request"].user, obj)

    def validate(self, attrs):
        loose = {k: attrs.pop(k) for k in services.SIZE_KEYS if k in attrs}
        if "defaults" in attrs and loose:
            raise ValidationError({"defaults": "Send either `defaults` or the size fields, not both."})
        if loose:
            attrs["defaults"] = loose
        if self.instance is None:
            missing = [k for k in ("category", "name") if not attrs.get(k)]
            if missing or "defaults" not in attrs:
                raise ValidationError({**{k: "is required" for k in missing}, **({} if "defaults" in attrs else {"width": "width, height and depth are required"})})
        return attrs


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=False)
    view = serializers.ChoiceField(choices=FurnitureImage.View.choices, required=False)
    image = serializers.ImageField(required=False)


class ReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["approved", "rejected"])
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")


class OwnerOrAdminCanWrite(BasePermission):
    """Checked before the body is validated, so a stranger gets 403 whatever they send."""

    message = "Only the workshop that owns this item (or a platform administrator) can change it."

    def has_object_permission(self, request, view, obj):
        return request.method in SAFE_METHODS or services.can_manage(request.user, obj)


class TemplateViewSet(viewsets.ModelViewSet):
    """Furniture catalogue. Everybody signed in sees approved items; a workshop owner also sees (and manages) their own items in any state.
    New items from workshops start `pending` and become visible to others once an administrator approves them."""

    serializer_class = TemplateSerializer
    permission_classes = [IsAuthenticated, OwnerOrAdminCanWrite]
    filterset_fields = ["category", "workshop", "status", "is_available"]
    search_fields = ["name", "description", "manufacturer", "material"]
    ordering_fields = ["name", "price", "category", "created_at"]
    pagination_class = None
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        return services.visible(self.request.user)

    def perform_create(self, serializer):
        serializer.instance = services.create_item(self.request.user, dict(serializer.validated_data))

    def perform_update(self, serializer):
        serializer.instance = services.update_item(self.request.user, self.get_object(), dict(serializer.validated_data))

    def perform_destroy(self, instance):
        services.deactivate_item(self.request.user, instance)

    @extend_schema(request=ReviewSerializer, responses=TemplateSerializer)
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        """Administrators approve or reject a workshop's item (a rejection needs a reason)."""
        s = ReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        item = services.review_item(request.user, self.get_object(), s.validated_data["status"], s.validated_data["note"])
        return Response(self.get_serializer(item).data)

    @extend_schema(request={"multipart/form-data": UploadSerializer}, responses=TemplateSerializer)
    @action(detail=True, methods=["post", "delete"], url_path="images")
    def images(self, request, pk=None):
        """POST `view` + `image` stores (or replaces) one side; DELETE `?view=front` removes it."""
        item = self.get_object()
        services.require_manage(request.user, item)
        if request.method == "DELETE":
            deleted, _ = item.images.filter(view=request.query_params.get("view", "")).delete()
            if not deleted:
                raise ValidationError({"view": "There is no image for this side."})
        else:
            s = UploadSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            view, img = s.validated_data.get("view"), s.validated_data.get("image")
            if not view or img is None:
                raise ValidationError({"view" if not view else "image": "is required"})
            validate_image(img)
            old = item.images.filter(view=view).first()
            if old:
                old.image.delete(save=False)
                old.image = img
                old.save()
            else:
                FurnitureImage.objects.create(template=item, view=view, image=img)
            services.touch(item, "catalog.image")
        return Response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data)

    @extend_schema(request={"multipart/form-data": UploadSerializer}, responses=TemplateSerializer)
    @action(detail=True, methods=["post", "delete"], url_path="model")
    def model(self, request, pk=None):
        """POST a `.glb` as `file` (validated; changes send an approved item back to review); DELETE returns to the generated model."""
        item = self.get_object()
        services.require_manage(request.user, item)
        if request.method == "DELETE":
            if item.glb_file:
                item.glb_file.delete(save=False)
                services.update_item(request.user, item, {"glb_file": ""})
        else:
            f = request.FILES.get("file")
            if f is None:
                raise ValidationError({"file": "is required"})
            try:
                info = glb.validate_glb(f.read())
            except glb.GlbError as e:
                raise ValidationError({"file": str(e)})
            f.seek(0)
            if item.glb_file:
                item.glb_file.delete(save=False)
            f.name = f"{item.slug}.glb"
            services.update_item(request.user, item, {"glb_file": f})
            item.refresh_from_db()
        return Response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data)

    @extend_schema(responses=OpenApiTypes.BINARY)
    @action(detail=True, methods=["get"], url_path=r"export/(?P<fmt>glb|gltf)")
    def export(self, request, pk=None, fmt="glb"):
        """The uploaded model (GLB), or a model generated from the item's sizes. Parametric models are plain boxes, not photo-real."""
        item = self.get_object()
        if item.glb_file and fmt == "glb":
            return FileResponse(item.glb_file.open("rb"), as_attachment=True, filename=f"{item.slug}.glb", content_type="model/gltf-binary")
        if item.glb_file:
            raise ValidationError({"format": "This item has an uploaded GLB; download it as glb."})
        boxes = builder.build_cabinet({**item.defaults, "material": "MDF"}, color=item.color or None)["boxes"]
        if fmt == "glb":
            return HttpResponse(exporters.to_glb(boxes), content_type="model/gltf-binary", headers={"Content-Disposition": f'attachment; filename="{item.slug}.glb"'})
        return HttpResponse(exporters.to_gltf(boxes), content_type="model/gltf+json", headers={"Content-Disposition": f'attachment; filename="{item.slug}.gltf"'})


class ImageFileView(APIView):
    """Public but bound to one image by a signature, so <img> and mobile image widgets work without headers."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=OpenApiTypes.BINARY)
    def get(self, request, pk):
        if not verify_file(request.query_params.get("sig", ""), IMAGE_KIND, pk):
            raise Http404
        img = FurnitureImage.objects.filter(pk=pk, template__is_active=True).first()
        if not img:
            raise Http404
        return FileResponse(img.image.open("rb"))


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
def categories(request):
    return Response(CATEGORIES)
