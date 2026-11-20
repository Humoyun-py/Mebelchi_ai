from rest_framework.permissions import BasePermission, IsAuthenticated


class IsOwner(BasePermission):
    """Object-level: the object's `owner` must be the requesting user."""

    def has_object_permission(self, request, view, obj):
        return getattr(obj, "owner_id", None) == request.user.id


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_staff or u.is_superuser))


class IsFurnitureMaker(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.role == "maker" or u.is_staff))


__all__ = ["IsOwner", "IsPlatformAdmin", "IsFurnitureMaker", "IsAuthenticated"]
