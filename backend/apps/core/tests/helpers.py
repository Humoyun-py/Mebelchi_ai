from rest_framework.test import APIClient

from apps.users.models import User


def make_user(email="a@example.com", role="maker", **kw):
    return User.objects.create_user(email=email, password="StrongPass!234", first_name="Test", last_name="User",
                                    role=role, role_selected=True, **kw)


def client_for(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user)
    return c


CAB = dict(width=800, height=2000, depth=400, thickness=18, shelves=3, doors=2, drawers=0)
