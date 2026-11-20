from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.analytics.services import feature_enabled
from apps.core.throttles import AuthRateThrottle
from apps.notifications.services import notify
from apps.subscriptions.services import ensure_subscription
from apps.users.serializers import UserSerializer

from . import services
from .serializers import (LoginSerializer, LogoutSerializer, PasswordResetConfirmSerializer, PasswordResetSerializer,
                          RegisterSerializer)


class RegisterView(CreateAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        if not feature_enabled('registration'):
            raise PermissionDenied('Registration is currently disabled.')
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        ensure_subscription(user)
        notify(user, 'Welcome to MEBELCHI AI', 'Choose your experience to get started.', 'success')
        refresh = RefreshToken.for_user(user)
        return Response({"user": UserSerializer(user).data, "access": str(refresh.access_token), "refresh": str(refresh)},
                        status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]
    serializer_class = LoginSerializer


class RefreshView(TokenRefreshView):
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]


class LogoutView(APIView):
    @extend_schema(request=LogoutSerializer, responses={204: None})
    def post(self, request):
        s = LogoutSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            RefreshToken(s.validated_data["refresh"]).blacklist()
        except TokenError:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    @extend_schema(request=PasswordResetSerializer, responses={202: None})
    def post(self, request):
        s = PasswordResetSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.send_reset_email(s.validated_data["email"])
        return Response({"detail": "If the account exists, a reset email has been sent."}, status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    @extend_schema(request=PasswordResetConfirmSerializer, responses={204: None})
    def post(self, request):
        s = PasswordResetConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = services.resolve_reset(s.validated_data["uid"], s.validated_data["token"])
        if not user:
            raise ValidationError({"token": "Invalid or expired reset link."})
        try:
            validate_password(s.validated_data["new_password"], user)
        except DjangoValidationError as e:
            raise ValidationError({"new_password": list(e.messages)})
        user.set_password(s.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class GoogleConfigView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        from django.conf import settings
        return Response({"google_client_id": settings.GOOGLE_CLIENT_ID or None})


class GoogleLoginView(APIView):
    """Sign in or register with a Google ID token (the email must be verified by Google)."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        from django.utils.crypto import get_random_string
        from apps.users.models import User
        claims = services.verify_google_credential(str(request.data.get("credential", "")))
        if not claims:
            raise ValidationError({"credential": "Google sign-in failed or is not configured."})
        email = claims["email"].lower()
        user = User.objects.filter(email__iexact=email).first()
        created = False
        if user is None:
            if not feature_enabled("registration"):
                raise PermissionDenied("Registration is currently disabled.")
            user = User.objects.create_user(email=email, password=get_random_string(40), first_name=(claims.get("given_name") or email.split("@")[0])[:80],
                                            last_name=(claims.get("family_name") or "")[:80])
            ensure_subscription(user)
            notify(user, "Welcome to MEBELCHI AI", "Choose your experience to get started.", "success")
            created = True
        elif not user.is_active:
            raise PermissionDenied("This account is disabled.")
        refresh = RefreshToken.for_user(user)
        return Response({"user": UserSerializer(user).data, "access": str(refresh.access_token), "refresh": str(refresh), "created": created})
