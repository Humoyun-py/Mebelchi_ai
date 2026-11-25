"""Business rules for workshops, members, orders and tasks. Views stay thin; every multi-step change runs in one transaction."""
from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import save_with_event
from apps.notifications.services import notify
from apps.users.models import User

from . import access
from .models import Order, OrderStatusChange, Task, TaskStatusChange, Workshop, WorkshopMember

M, O, T = WorkshopMember, Order, Task

ORDER_TRANSITIONS = {
    O.Status.NEW: {O.Status.CONFIRMED, O.Status.CANCELLED},
    O.Status.CONFIRMED: {O.Status.IN_PRODUCTION, O.Status.CANCELLED},
    O.Status.IN_PRODUCTION: {O.Status.READY, O.Status.CANCELLED},
    O.Status.READY: {O.Status.DELIVERED, O.Status.IN_PRODUCTION, O.Status.CANCELLED},
    O.Status.DELIVERED: set(),
    O.Status.CANCELLED: set(),
}
ORDER_TERMINAL = {O.Status.DELIVERED, O.Status.CANCELLED}
PAYMENT_FIELDS = {"paid_amount", "payment_status"}

OPEN_TASK = {T.Status.PENDING, T.Status.IN_PROGRESS, T.Status.REVIEW}
TASK_TRANSITIONS_OWNER = {
    T.Status.PENDING: {T.Status.IN_PROGRESS, T.Status.CANCELLED},
    T.Status.IN_PROGRESS: {T.Status.PENDING, T.Status.REVIEW, T.Status.COMPLETED, T.Status.CANCELLED},
    T.Status.REVIEW: {T.Status.IN_PROGRESS, T.Status.COMPLETED, T.Status.CANCELLED},
    T.Status.COMPLETED: set(),
    T.Status.CANCELLED: set(),
}
# An employee reports progress; only the owner can complete or cancel a task.
TASK_TRANSITIONS_ASSIGNEE = {
    T.Status.PENDING: {T.Status.IN_PROGRESS},
    T.Status.IN_PROGRESS: {T.Status.REVIEW},
    T.Status.REVIEW: {T.Status.IN_PROGRESS},
}


def allowed_order_statuses(order: Order, is_owner: bool) -> list[str]:
    """Next statuses the caller may choose (the UI renders buttons from this, so the rules live only here)."""
    if not is_owner or order.workshop.status != Workshop.Status.ACTIVE:
        return []
    return sorted(ORDER_TRANSITIONS[order.status])


def allowed_task_statuses(task: Task, *, is_owner: bool, is_assignee: bool) -> list[str]:
    if task.workshop.status != Workshop.Status.ACTIVE:
        return []
    if is_owner:
        return sorted(TASK_TRANSITIONS_OWNER[task.status])
    return sorted(TASK_TRANSITIONS_ASSIGNEE.get(task.status, set())) if is_assignee else []


def err(field: str, msg: str):
    return ValidationError({field: msg})


# ------------------------------------------------------------------------------------------------ workshops
def _unique_slug(name: str) -> str:
    base = (slugify(name) or "workshop")[:120]
    slug = base
    while Workshop.objects.filter(slug=slug).exists():
        slug = f"{base}-{get_random_string(4, 'abcdefghjkmnpqrstuvwxyz23456789')}"
    return slug


def create_workshop(user: User, data: dict) -> Workshop:
    if user.role != User.Role.WORKSHOP:
        raise PermissionDenied("Only accounts with the Workshop role can create a workshop. A platform administrator assigns that role; "
                               "being an administrator does not replace it.")
    data = {k: v for k, v in data.items() if k != "status"}          # a new workshop is always pending, whatever the request says
    for attempt in range(3):
        try:
            with transaction.atomic():
                ws = Workshop(owner=user, slug=_unique_slug(data["name"]), status=Workshop.Status.PENDING, **data)
                save_with_event(ws, "workshop.created")
                M.objects.create(workshop=ws, user=user, role=M.Role.OWNER, status=M.Status.ACTIVE, joined_at=timezone.now())
                return ws
        except IntegrityError:  # two requests picked the same slug at once: pick again
            if attempt == 2:
                raise
    raise AssertionError("unreachable")


def update_workshop(ws: Workshop, actor: User, data: dict) -> Workshop:
    access.require_owner(actor, ws)
    if ws.status == Workshop.Status.SUSPENDED:
        raise PermissionDenied("This workshop is suspended. Contact the platform administrators.")
    if "status" in data and ws.status not in (Workshop.Status.ACTIVE, Workshop.Status.INACTIVE):
        raise PermissionDenied("The status of a workshop that is waiting for approval is set by platform administrators.")
    for k, v in data.items():
        setattr(ws, k, v)
    save_with_event(ws, "workshop.updated")
    return ws


def review_workshop(ws: Workshop, actor: User, target: str) -> Workshop:
    """Platform administrators approve, suspend or reactivate a workshop (the views check that the caller is staff)."""
    allowed = {Workshop.Status.ACTIVE: {Workshop.Status.PENDING, Workshop.Status.SUSPENDED, Workshop.Status.INACTIVE},
               Workshop.Status.SUSPENDED: {Workshop.Status.ACTIVE, Workshop.Status.INACTIVE}}
    if ws.status not in allowed.get(target, set()):
        raise err("status", f"Cannot change status from '{ws.status}' to '{target}'.")
    previous = ws.status
    ws.status = target
    event = "workshop.approved" if previous == Workshop.Status.PENDING else "workshop.suspended" if target == Workshop.Status.SUSPENDED else "workshop.reactivated"
    with transaction.atomic():
        save_with_event(ws, event)
    notify(ws.owner, {"workshop.approved": "Your workshop was approved", "workshop.suspended": "Your workshop was suspended",
                      "workshop.reactivated": "Your workshop was reactivated"}[event], ws.name, "success" if target == Workshop.Status.ACTIVE else "warning")
    return ws


def delete_workshop(ws: Workshop, actor: User):
    access.require_owner(actor, ws)
    if ws.orders.exists() or ws.tasks.exists():
        raise ConflictError("A workshop with orders or tasks cannot be deleted because their records must be kept. Set its status to inactive instead.")
    ws._audit_event = "workshop.deleted"
    ws.delete()


class ConflictError(Exception):
    """Mapped to HTTP 409 by the API layer."""


# ------------------------------------------------------------------------------------------------ members
def invite_member(ws: Workshop, actor: User, email: str) -> WorkshopMember:
    access.require_owner(actor, ws)
    access.require_writable(ws)
    user = User.objects.filter(email__iexact=email.strip(), is_active=True).first()
    if user is None:
        raise err("email", "No active MEBELCHI AI account uses this email. Ask the person to register first.")
    with transaction.atomic():
        m = M.objects.select_for_update().filter(workshop=ws, user=user).first()
        if m is None:
            m = M(workshop=ws, user=user)
        elif m.status == M.Status.ACTIVE:
            raise err("email", "This person is already a member of the workshop.")
        elif m.status == M.Status.INVITED:
            raise err("email", "This person has already been invited.")
        m.role, m.status, m.invited_by, m.removed_at, m.joined_at = M.Role.EMPLOYEE, M.Status.INVITED, actor, None, None
        save_with_event(m, "member.invited")
    notify(user, f"Invitation to {ws.name}", f"{actor.full_name} invited you to join the workshop \"{ws.name}\". Accept it from your invitations.", "info")
    return m


def accept_invitation(m: WorkshopMember, actor: User) -> WorkshopMember:
    if m.user_id != actor.id or m.status != M.Status.INVITED:
        raise PermissionDenied("This invitation cannot be accepted.")
    if m.workshop.status != Workshop.Status.ACTIVE:
        raise PermissionDenied("This workshop is not accepting new members right now.")
    m.status, m.joined_at = M.Status.ACTIVE, timezone.now()
    save_with_event(m, "member.accepted")
    return m


def remove_member(m: WorkshopMember, actor: User, *, event: str = "member.removed") -> WorkshopMember:
    """Soft removal: the row stays (status `removed`) so orders, tasks and history keep their references."""
    if m.role == M.Role.OWNER:
        raise err("detail", "The owner cannot be removed. Transfer ownership to another member first.")
    if m.status == M.Status.REMOVED:
        raise err("detail", "This member has already been removed.")
    m.status, m.removed_at = M.Status.REMOVED, timezone.now()
    save_with_event(m, event)
    return m


def transfer_ownership(ws: Workshop, actor: User, target: WorkshopMember) -> WorkshopMember:
    access.require_owner(actor, ws)
    if target.workshop_id != ws.id or target.status != M.Status.ACTIVE or target.role != M.Role.EMPLOYEE:
        raise err("role", "Ownership can only be transferred to an active employee of this workshop.")
    with transaction.atomic():
        current = M.objects.select_for_update().get(workshop=ws, role=M.Role.OWNER)
        # demote first: there must never be two owner rows (unique constraint) nor zero owners after the transaction
        current.role = M.Role.EMPLOYEE
        # the owner CHECK constraint only applies to owners, an ex-owner stays an active employee
        save_with_event(current, "member.role_changed")
        target.role = M.Role.OWNER
        save_with_event(target, "member.role_changed")
        ws.owner = target.user
        save_with_event(ws, "workshop.owner_changed")
    return target


# ------------------------------------------------------------------------------------------------ orders
def next_order_number(ws: Workshop) -> str:
    """Atomic per-workshop sequence: the UPDATE takes the row lock, so concurrent creators get different numbers."""
    Workshop.objects.filter(pk=ws.pk).update(order_counter=F("order_counter") + 1)
    n = Workshop.objects.filter(pk=ws.pk).values_list("order_counter", flat=True).get()
    return f"ORD-{ws.pk:04d}-{n:06d}"


def derive_payment_status(total: Decimal, paid: Decimal, current: str) -> str:
    if current == O.PaymentStatus.REFUNDED:
        return current
    if paid <= 0:
        return O.PaymentStatus.UNPAID
    return O.PaymentStatus.PAID if paid >= total else O.PaymentStatus.PARTIALLY_PAID


def _active_member(ws: Workshop, member: WorkshopMember | None, field: str):
    if member is not None and (member.workshop_id != ws.id or member.status != M.Status.ACTIVE):
        raise err(field, "Must be an active member of this workshop.")


def _check_project(actor: User, project):
    if project is not None and project.owner_id != actor.id:
        raise err("related_project", "You can only attach your own projects.")


def _check_dates(start, deadline, *, creating_or_changing_deadline: bool):
    if start and deadline and deadline < start:
        raise err("deadline", "The deadline cannot be before the start date.")
    if deadline and creating_or_changing_deadline and deadline < timezone.localdate():
        raise err("deadline", "The deadline cannot be in the past.")


def _log_order(order: Order, from_status: str, actor: User, note: str = ""):
    OrderStatusChange.objects.create(order=order, from_status=from_status, to_status=order.status, changed_by=actor, note=note[:255])


def create_order(ws: Workshop, actor: User, data: dict) -> Order:
    access.require_owner(actor, ws)
    access.require_writable(ws)
    data = dict(data)
    paid = data.get("paid_amount", Decimal("0"))
    total = data.get("total_price", Decimal("0"))
    if paid > total:
        raise err("paid_amount", "The paid amount cannot exceed the total price.")
    _active_member(ws, data.get("assigned_employee"), "assigned_employee")
    _check_project(actor, data.get("related_project"))
    _check_dates(data.get("start_date"), data.get("deadline"), creating_or_changing_deadline=True)
    data.pop("status", None)
    data.pop("payment_status", None)
    with transaction.atomic():
        order = Order(workshop=ws, created_by=actor, order_number=next_order_number(ws), status=O.Status.NEW,
                      payment_status=derive_payment_status(total, paid, ""), **data)
        save_with_event(order, "order.created")
        _log_order(order, "", actor, "Order created")
    return order


def update_order(order: Order, actor: User, data: dict) -> Order:
    ws = order.workshop
    access.require_owner(actor, ws)
    access.require_writable(ws)
    data = dict(data)
    note = data.pop("status_note", "")
    old_status = order.status
    new_status = data.pop("status", old_status)
    if order.status in ORDER_TERMINAL:
        locked = sorted(set(data) - PAYMENT_FIELDS)
        if locked or new_status != old_status:
            raise ValidationError({(locked or ["status"])[0]: f"A {order.status} order can no longer be edited; only its payment can be updated."})
    if new_status != old_status and new_status not in ORDER_TRANSITIONS[old_status]:
        allowed = ", ".join(sorted(ORDER_TRANSITIONS[old_status])) or "none"
        raise err("status", f"An order cannot go from {old_status} to {new_status}. Allowed next statuses: {allowed}.")

    _active_member(ws, data.get("assigned_employee"), "assigned_employee")
    if "related_project" in data:
        _check_project(actor, data["related_project"])
    start = data.get("start_date", order.start_date)
    deadline = data.get("deadline", order.deadline)
    _check_dates(start, deadline, creating_or_changing_deadline="deadline" in data and data["deadline"] != order.deadline)

    total = data.get("total_price", order.total_price)
    paid = data.get("paid_amount", order.paid_amount)
    if paid > total:
        raise err("paid_amount" if "paid_amount" in data else "total_price", "The paid amount cannot exceed the total price.")
    requested = data.pop("payment_status", None)
    if order.payment_status == O.PaymentStatus.REFUNDED:
        if requested not in (None, O.PaymentStatus.REFUNDED) or {"paid_amount", "total_price"} & set(data):
            raise err("payment_status", "A refunded order's payment record is closed.")
        pay_status = O.PaymentStatus.REFUNDED
    elif requested == O.PaymentStatus.REFUNDED:
        if paid <= 0:
            raise err("payment_status", "Nothing has been paid, so there is nothing to refund.")
        pay_status = O.PaymentStatus.REFUNDED
    else:
        pay_status = derive_payment_status(total, paid, "")
        if requested not in (None, pay_status):
            raise err("payment_status", f"The payment status follows the paid amount (here: {pay_status}). Send paid_amount instead.")

    with transaction.atomic():
        for k, v in data.items():
            setattr(order, k, v)
        order.payment_status = pay_status
        if new_status != old_status:
            _apply_order_status(order, new_status)
        event = "order.status_changed" if new_status != old_status else "order.updated"
        save_with_event(order, event)
        if new_status != old_status:
            _log_order(order, old_status, actor, note)
            if new_status == O.Status.CANCELLED:
                _cancel_open_tasks(order, actor)
    return order


def _apply_order_status(order: Order, new_status: str):
    order.status = new_status
    today = timezone.localdate()
    if new_status == O.Status.IN_PRODUCTION and order.start_date is None and (order.deadline is None or order.deadline >= today):
        order.start_date = today
    if new_status == O.Status.DELIVERED:
        order.completed_at = timezone.now()


def _cancel_open_tasks(order: Order, actor: User):
    for task in order.tasks.filter(status__in=OPEN_TASK):
        _set_task_status(task, T.Status.CANCELLED, actor, "Order cancelled", event="task.status_changed")


def delete_order(order: Order, actor: User):
    access.require_owner(actor, order.workshop)
    if order.status not in (O.Status.NEW, O.Status.CANCELLED) or order.paid_amount > 0:
        raise ConflictError("Only orders that are new or cancelled and have no payments can be deleted. Cancel the order to keep its record.")
    order._audit_event = "order.deleted"
    order.delete()


# ------------------------------------------------------------------------------------------------ tasks
def _check_task_deadline(deadline):
    if deadline is not None and deadline <= timezone.now():
        raise err("deadline", "The deadline must be in the future.")


def _set_task_status(task: Task, new_status: str, actor: User, note: str = "", *, event: str):
    old = task.status
    task.status = new_status
    now = timezone.now()
    if new_status == T.Status.IN_PROGRESS and task.started_at is None:
        task.started_at = now
    if new_status == T.Status.COMPLETED:
        task.completed_at = now
    save_with_event(task, event)
    TaskStatusChange.objects.create(task=task, from_status=old, to_status=new_status, changed_by=actor, note=note[:255])


def create_task(ws: Workshop, actor: User, data: dict) -> Task:
    access.require_owner(actor, ws)
    access.require_writable(ws)
    data = dict(data)
    order = data.get("order")
    if order is not None:
        if order.workshop_id != ws.id:
            raise err("order", "This order belongs to a different workshop.")
        if order.status in ORDER_TERMINAL:
            raise err("order", f"Tasks cannot be added to a {order.status} order.")
    _active_member(ws, data.get("assigned_to"), "assigned_to")
    _check_task_deadline(data.get("deadline"))
    for k in ("status", "started_at", "completed_at"):
        data.pop(k, None)
    with transaction.atomic():
        task = Task(workshop=ws, created_by=actor, status=T.Status.PENDING, **data)
        save_with_event(task, "task.created")
        TaskStatusChange.objects.create(task=task, from_status="", to_status=task.status, changed_by=actor, note="Task created")
    _notify_assignee(task, actor)
    return task


def update_task(task: Task, actor: User, data: dict) -> Task:
    ws = task.workshop
    owner = access.is_owner(actor, ws.pk)
    data = dict(data)
    note = data.pop("status_note", "")
    if not owner:
        me = access.membership(actor, ws.pk)
        if me is None or task.assigned_to_id != me.id:
            raise PermissionDenied("You can only update tasks assigned to you.")
        extra = sorted(set(data) - {"status"})
        if extra:
            raise PermissionDenied(f"Employees can only change the status of their tasks (not: {', '.join(extra)}).")
    access.require_writable(ws)

    old_status, old_assignee = task.status, task.assigned_to_id
    new_status = data.pop("status", old_status)
    if new_status != old_status:
        allowed = (TASK_TRANSITIONS_OWNER if owner else TASK_TRANSITIONS_ASSIGNEE).get(old_status, set())
        if new_status not in allowed:
            nxt = ", ".join(sorted(allowed)) or "none"
            raise err("status", f"A task cannot go from {old_status} to {new_status}{'' if owner else ' by an employee'}. Allowed next statuses: {nxt}.")
    if task.status in (T.Status.COMPLETED, T.Status.CANCELLED) and data:
        raise err(next(iter(data)), f"A {task.status} task can no longer be edited.")
    if "assigned_to" in data:
        _active_member(ws, data["assigned_to"], "assigned_to")
    if "deadline" in data and data["deadline"] != task.deadline:
        _check_task_deadline(data["deadline"])

    with transaction.atomic():
        for k, v in data.items():
            setattr(task, k, v)
        reassigned = task.assigned_to_id != old_assignee
        if new_status != old_status:
            event = "task.completed" if new_status == T.Status.COMPLETED else "task.assigned" if reassigned else "task.status_changed"
            _set_task_status(task, new_status, actor, note, event=event)
        else:
            save_with_event(task, "task.assigned" if reassigned else "task.updated")
    if reassigned:
        _notify_assignee(task, actor)
    return task


def delete_task(task: Task, actor: User):
    access.require_owner(actor, task.workshop)
    if task.started_at is not None or task.status not in (T.Status.PENDING, T.Status.CANCELLED):
        raise ConflictError("A task that has been worked on cannot be deleted. Cancel it to keep its history.")
    task._audit_event = "task.deleted"
    task.delete()


def _notify_assignee(task: Task, actor: User):
    m = task.assigned_to
    if m is not None and m.user_id != actor.id:
        notify(m.user, "New task assigned", f"{task.title} ({task.workshop.name})", "info")


# ------------------------------------------------------------------------------------------------ statistics
def workshop_statistics(ws: Workshop) -> dict:
    """All figures come from the database with a fixed number of aggregate queries (no per-row work)."""
    now = timezone.now()
    money = DecimalField(max_digits=14, decimal_places=2)
    zero = Value(Decimal("0"), output_field=money)
    live = ~Q(status=O.Status.CANCELLED)
    open_money = live & ~Q(payment_status=O.PaymentStatus.REFUNDED)
    o = Order.objects.filter(workshop=ws).aggregate(
        total=Count("id"),
        new=Count("id", filter=Q(status=O.Status.NEW)),
        confirmed=Count("id", filter=Q(status=O.Status.CONFIRMED)),
        in_production=Count("id", filter=Q(status=O.Status.IN_PRODUCTION)),
        ready=Count("id", filter=Q(status=O.Status.READY)),
        delivered=Count("id", filter=Q(status=O.Status.DELIVERED)),
        cancelled=Count("id", filter=Q(status=O.Status.CANCELLED)),
        total_value=Coalesce(Sum("total_price", filter=live), zero),
        paid=Coalesce(Sum("paid_amount", filter=~Q(payment_status=O.PaymentStatus.REFUNDED)), zero),
        outstanding=Coalesce(Sum(ExpressionWrapper(F("total_price") - F("paid_amount"), output_field=money), filter=open_money), zero),
    )
    t = Task.objects.filter(workshop=ws).aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status=T.Status.PENDING)),
        in_progress=Count("id", filter=Q(status=T.Status.IN_PROGRESS)),
        review=Count("id", filter=Q(status=T.Status.REVIEW)),
        completed=Count("id", filter=Q(status=T.Status.COMPLETED)),
        cancelled=Count("id", filter=Q(status=T.Status.CANCELLED)),
        overdue=Count("id", filter=Q(status__in=OPEN_TASK, deadline__lt=now)),
    )
    e = WorkshopMember.objects.filter(workshop=ws, role=M.Role.EMPLOYEE).aggregate(
        total=Count("id", filter=Q(status__in=[M.Status.ACTIVE, M.Status.INVITED])),
        active=Count("id", filter=Q(status=M.Status.ACTIVE)),
        invited=Count("id", filter=Q(status=M.Status.INVITED)),
    )
    return {
        "workshop": ws.pk,
        "generated_at": now,
        "orders": {"total": o["total"], "new": o["new"], "confirmed": o["confirmed"], "in_production": o["in_production"], "ready": o["ready"],
                   "delivered": o["delivered"], "completed": o["delivered"], "cancelled": o["cancelled"]},
        "employees": e,
        "tasks": t,
        "money": {"total_order_value": o["total_value"], "paid_amount": o["paid"], "outstanding_amount": o["outstanding"],
                  "note": "Order value excludes cancelled orders; paid excludes refunded orders; outstanding = total - paid over orders that "
                          "are neither cancelled nor refunded. Amounts are the sums recorded on orders, not bank data."},
    }
