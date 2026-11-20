from django.http import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from django.utils import timezone

from apps.core.signing import verify_file

from .models import User
from .serializers import AvatarSerializer, PasswordChangeSerializer, RoleSerializer, UserSerializer


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


class RoleView(APIView):
    @extend_schema(request=RoleSerializer, responses=UserSerializer)
    def post(self, request):
        s = RoleSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        request.user.role = s.validated_data["role"]
        request.user.role_selected = True
        request.user.save(update_fields=["role", "role_selected"])
        return Response(UserSerializer(request.user).data)


class AvatarView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=AvatarSerializer, responses=UserSerializer)
    def post(self, request):
        s = AvatarSerializer(request.user, data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def delete(self, request):
        request.user.avatar.delete(save=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AvatarFileView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes: list = []  # cheap/static or signature-protected: the anonymous per-IP limit would break shared networks

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def get(self, request, pk):
        if not verify_file(request.query_params.get("sig", ""), "avatar", pk):
            raise Http404
        user = User.objects.filter(pk=pk).exclude(avatar="").first()
        if not user:
            raise Http404
        return FileResponse(user.avatar.open("rb"))


class PasswordChangeView(APIView):
    @extend_schema(request=PasswordChangeSerializer, responses={204: None})
    def post(self, request):
        s = PasswordChangeSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        request.user.set_password(s.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionsView(APIView):
    """Active sessions == non-expired, non-blacklisted refresh tokens."""

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        black = BlacklistedToken.objects.values_list("token_id", flat=True)
        qs = OutstandingToken.objects.filter(user=request.user, expires_at__gt=timezone.now()).exclude(id__in=black).order_by("-created_at")
        return Response([{"id": t.id, "created_at": t.created_at, "expires_at": t.expires_at} for t in qs])

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def delete(self, request):
        """Revoke all sessions (user must log in again everywhere)."""
        n = 0
        for t in OutstandingToken.objects.filter(user=request.user):
            _, created = BlacklistedToken.objects.get_or_create(token=t)
            n += int(created)
        return Response({"revoked": n})


class SessionDetailView(APIView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def delete(self, request, pk):
        token = OutstandingToken.objects.filter(user=request.user, pk=pk).first()
        if not token:
            raise Http404
        BlacklistedToken.objects.get_or_create(token=token)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StorageView(APIView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        from apps.files.services import storage_summary
        return Response(storage_summary(request.user))
