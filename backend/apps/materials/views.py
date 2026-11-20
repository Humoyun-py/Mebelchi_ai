from django.db.models import Q
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .models import Material
from .serializers import MaterialSerializer


class MaterialViewSet(viewsets.ModelViewSet):
    """System materials are read-only; users manage their own."""

    serializer_class = MaterialSerializer
    permission_classes = [IsAuthenticated]
    queryset = Material.objects.all()
    filterset_fields = ["kind", "thickness"]
    search_fields = ["name"]
    pagination_class = None

    def get_queryset(self):
        return Material.objects.filter(Q(is_system=True) | Q(owner=self.request.user))

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, is_system=False)

    def _check(self, obj):
        if obj.is_system or obj.owner_id != self.request.user.id:
            raise PermissionDenied("System materials cannot be modified.")

    def perform_update(self, serializer):
        self._check(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._check(instance)
        instance.delete()
