from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.core.permissions import IsWorkshop

from .models import Workshop
from .serializers import WorkshopSerializer


class WorkshopMeView(APIView):
    """The signed-in workshop's own profile. Other accounts get 403, and no one can read another profile here."""

    permission_classes = [IsAuthenticated, IsWorkshop]

    def _profile(self, request) -> Workshop:
        profile = Workshop.objects.filter(owner=request.user).first()
        if profile is None:
            raise NotFound("Workshop profile does not exist yet.")
        return profile

    @extend_schema(responses=WorkshopSerializer)
    def get(self, request):
        return Response(WorkshopSerializer(self._profile(request)).data)

    @extend_schema(request=WorkshopSerializer, responses=WorkshopSerializer)
    def post(self, request):
        if Workshop.objects.filter(owner=request.user).exists():
            raise ValidationError({"detail": "Profile already exists. Use PATCH."})
        s = WorkshopSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        with transaction.atomic():
            profile = Workshop.objects.create(owner=request.user, **s.validated_data)
            audit.record("workshop.profile_created", actor=request.user, target_type="workshop", target_id=profile.pk)
        return Response(WorkshopSerializer(profile).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=WorkshopSerializer, responses=WorkshopSerializer)
    def patch(self, request):
        profile = self._profile(request)
        s = WorkshopSerializer(profile, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(WorkshopSerializer(profile).data)
