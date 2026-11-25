"""Who may see and do what. Every endpoint goes through these helpers; nothing relies on the frontend.

Rules
- Only an *active* membership grants access. Invited and removed members see nothing of the workshop.
- Owners see and manage everything of their workshop.
- Employees see only what concerns them: the tasks assigned to them, and the orders assigned to them or containing a task
  assigned to them. Employees never see order money fields. There is no cross-workshop access and no staff bypass.
- Objects the user may not see are answered with 404 (indistinguishable from "does not exist"); objects they may see but
  not change are answered with 403.
"""
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from .models import Order, Task, Workshop, WorkshopMember

M = WorkshopMember


def active_memberships(user):
    return M.objects.filter(user=user, status=M.Status.ACTIVE)


def owner_workshop_ids(user):
    """Subquery of workshop ids the user owns (active owner membership)."""
    return active_memberships(user).filter(role=M.Role.OWNER).values("workshop_id")


def my_member_ids(user):
    return active_memberships(user).values("id")


def membership(user, workshop_id) -> WorkshopMember | None:
    if not getattr(user, "is_authenticated", False):
        return None
    return active_memberships(user).filter(workshop_id=workshop_id).first()


def is_owner(user, workshop_id) -> bool:
    m = membership(user, workshop_id)
    return bool(m and m.role == M.Role.OWNER)


def require_owner(user, workshop):
    if not is_owner(user, workshop.pk):
        raise PermissionDenied("Only the workshop owner can do this.")


def require_writable(workshop):
    """Inactive and suspended workshops are read-only for everybody."""
    if workshop.status != Workshop.Status.ACTIVE:
        raise PermissionDenied({"pending": "This workshop is waiting for administrator approval; orders, tasks and invitations open once it is approved.",
                                "inactive": "This workshop is inactive; reactivate it before making changes."}.get(workshop.status,
                               "This workshop is suspended. Contact the platform administrators."))


def visible_workshops(user):
    return Workshop.objects.filter(members__user=user, members__status=M.Status.ACTIVE).distinct()


def visible_orders(user):
    mine = my_member_ids(user)
    return Order.objects.filter(Q(workshop_id__in=owner_workshop_ids(user)) | Q(assigned_employee_id__in=mine)
                                | Q(pk__in=Task.objects.filter(assigned_to_id__in=mine, order__isnull=False).values("order_id")))


def visible_tasks(user):
    return Task.objects.filter(Q(workshop_id__in=owner_workshop_ids(user)) | Q(assigned_to_id__in=my_member_ids(user)))
