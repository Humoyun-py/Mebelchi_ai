from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.audit import services as audit
from apps.users.models import User
from apps.users.serializers import UserSerializer


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "password", "confirm_password"]

    def validate_email(self, v):
        v = v.lower()
        if User.objects.filter(email__iexact=v).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return v

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("confirm_password"):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        validate_password(attrs["password"], User(**{k: v for k, v in attrs.items() if k != "password"}))
        return attrs

    def create(self, data):
        return User.objects.create_user(**data)


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        attrs["email"] = attrs.get("email", "").lower()
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        audit.record("login", model="users.user", object_id=self.user.pk, object_repr=self.user.email, actor=self.user)
        return data


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
