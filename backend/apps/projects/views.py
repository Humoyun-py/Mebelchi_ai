from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.views import OwnedModelViewSet
from apps.subscriptions.services import enforce_project_limit

from . import services
from .models import Project
from .serializers import ActivitySerializer, ProjectSerializer


class ProjectViewSet(OwnedModelViewSet):
    queryset = Project.objects.select_related("material", "folder")
    serializer_class = ProjectSerializer
    filterset_fields = ["status", "category", "pinned", "folder"]
    search_fields = ["name", "description"]
    ordering_fields = ["updated_at", "created_at", "name"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "list" and "status" not in self.request.query_params:
            qs = qs.filter(status=Project.Status.ACTIVE)
        return qs

    def perform_create(self, serializer):
        enforce_project_limit(self.request.user)
        super().perform_create(serializer)
        services.log(serializer.instance, "created")

    def perform_update(self, serializer):
        serializer.save()
        services.log(serializer.instance, "updated", ", ".join(serializer.validated_data.keys()))

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        enforce_project_limit(request.user)
        return Response(self.get_serializer(services.duplicate(self.get_object())).data, status=201)

    def _set(self, request, **fields):
        p = self.get_object()
        for k, v in fields.items():
            setattr(p, k, v)
        p.save()
        return p

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        p = self._set(request, status=Project.Status.ARCHIVED)
        services.log(p, "archived")
        return Response(self.get_serializer(p).data)

    @action(detail=True, methods=["post"])
    def unarchive(self, request, pk=None):
        enforce_project_limit(request.user)
        p = self._set(request, status=Project.Status.ACTIVE)
        services.log(p, "unarchived")
        return Response(self.get_serializer(p).data)

    @action(detail=True, methods=["post"])
    def pin(self, request, pk=None):
        p = self.get_object()
        p.pinned = not p.pinned
        p.save(update_fields=["pinned", "updated_at"])
        return Response(self.get_serializer(p).data)

    @action(detail=True, methods=["get"])
    def activity(self, request, pk=None):
        return Response(ActivitySerializer(self.get_object().activities.all()[:50], many=True).data)
