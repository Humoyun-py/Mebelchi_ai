from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .permissions import IsOwner


class OwnedModelViewSet(viewsets.ModelViewSet):
    """Scopes every query to the requesting user and stamps owner on create."""

    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
