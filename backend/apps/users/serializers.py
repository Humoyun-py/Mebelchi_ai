from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()
    phone_verified = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "full_name", "phone", "phone_verified", "avatar_url", "role", "role_selected",
                  "theme", "language", "notify_email", "notify_system", "is_admin", "date_joined"]
        read_only_fields = ["id", "email", "role", "role_selected", "date_joined"]

    def get_avatar_url(self, obj):
        if not obj.avatar:
            return None
        from apps.core.signing import sign_file
        return f"/api/v1/users/{obj.pk}/avatar/?sig={sign_file('avatar', obj.pk)}"

    def get_is_admin(self, obj):
        return obj.is_staff or obj.is_superuser

    def get_phone_verified(self, obj):
        return obj.phone_verified_at is not None

    def update(self, instance, validated_data):
        # a changed number is no longer the verified one
        if "phone" in validated_data and validated_data["phone"] != instance.phone:
            instance.phone_verified_at = None
        return super().update(instance, validated_data)


class RoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.SELF_SELECTABLE_ROLES)


class AvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["avatar"]


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, v):
        if not self.context["request"].user.check_password(v):
            raise serializers.ValidationError("Current password is incorrect.")
        return v

    def validate_new_password(self, v):
        validate_password(v, self.context["request"].user)
        return v
