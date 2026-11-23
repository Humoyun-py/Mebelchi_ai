from rest_framework.permissions import BasePermission, IsAuthenticated


def _role(request) -> str | None:
    u = getattr(request, "user", None)
    return getattr(u, "role", None) if u and u.is_authenticated else None


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


class IsHomeOwner(BasePermission):
    def has_permission(self, request, view):
        return _role(request) == "homeowner"


class IsWorkshop(BasePermission):
    """Only accounts with the workshop role. Admin status does not grant workshop actions by itself."""

    def has_permission(self, request, view):
        return _role(request) == "workshop"


__all__ = ["IsOwner", "IsPlatformAdmin", "IsFurnitureMaker", "IsHomeOwner", "IsWorkshop", "IsAuthenticated"]
