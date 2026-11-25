"""Workshop management: workshops, members, orders and tasks.

Ownership model
- `Workshop` is the tenant. Every `Order` and `Task` belongs to exactly one workshop (PROTECT: a workshop that has business
  records cannot be deleted, it can only be deactivated).
- Who may do what comes from `WorkshopMember` (role owner/employee, status invited/active/removed). Members are never
  deleted when somebody leaves: they are marked `removed`, so orders, tasks and history keep pointing at a real row.
- People on orders/tasks are referenced through `WorkshopMember` (not `User`), so "assigned to" always means "a member of this workshop".

Customers are stored on the order for now (name, contact, optional platform account). A future CRM module can extract a
`Customer` table from these columns with a data migration.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.validators import validate_image

MONEY = dict(max_digits=12, decimal_places=2)


class Workshop(models.Model):
    class Kind(models.TextChoices):
        INDIVIDUAL = "individual", "Individual master"
        WORKSHOP = "workshop", "Workshop"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"     # every new workshop starts here; a platform administrator approves it
        ACTIVE = "active", "Active"                 # approved and operating
        INACTIVE = "inactive", "Inactive"           # paused by its owner (read-only)
        SUSPENDED = "suspended", "Suspended"        # frozen by a platform administrator

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.WORKSHOP)
    city = models.CharField(max_length=80, blank=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_workshops")
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    logo = models.ImageField(upload_to="workshops/", blank=True, validators=[validate_image])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    # Last issued order sequence number. Incremented with a single atomic UPDATE (see services.next_order_number).
    order_counter = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [models.Index(fields=["owner"]), models.Index(fields=["status"])]

    def __str__(self):
        return self.name


class WorkshopMember(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        EMPLOYEE = "employee", "Employee"

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        REMOVED = "removed", "Removed"

    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workshop_memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EMPLOYEE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.INVITED)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    joined_at = models.DateTimeField(null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["role", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["workshop", "user"], name="uniq_member_per_workshop_user"),
            # a workshop has at most one owner row, and the owner row is always an active membership
            models.UniqueConstraint(fields=["workshop"], condition=Q(role="owner"), name="uniq_owner_per_workshop"),
            models.CheckConstraint(condition=~Q(role="owner") | Q(status="active"), name="owner_membership_is_active"),
        ]
        indexes = [models.Index(fields=["user", "status"]), models.Index(fields=["workshop", "status", "role"])]

    def __str__(self):
        cache = self._state.fields_cache  # only relations that are already loaded: a label must never cost a query
        user, ws = cache.get("user"), cache.get("workshop")
        return f"{user.email if user else f'user {self.user_id}'} in {ws.name if ws else f'workshop {self.workshop_id}'} ({self.role})"

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONFIRMED = "confirmed", "Confirmed"
        IN_PRODUCTION = "in_production", "In production"
        READY = "ready", "Ready"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIALLY_PAID = "partially_paid", "Partially paid"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"

    order_number = models.CharField(max_length=32, unique=True)
    workshop = models.ForeignKey(Workshop, on_delete=models.PROTECT, related_name="orders")
    customer_name = models.CharField(max_length=160)
    customer_phone = models.CharField(max_length=32, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_address = models.CharField(max_length=255, blank=True)
    customer_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                      help_text="Optional platform account of the customer")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    related_project = models.ForeignKey("projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="workshop_orders")
    total_price = models.DecimalField(default=0, **MONEY)
    paid_amount = models.DecimalField(default=0, **MONEY)
    payment_status = models.CharField(max_length=16, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.NEW)
    assigned_employee = models.ForeignKey(WorkshopMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_orders")
    start_date = models.DateField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(total_price__gte=0), name="order_total_non_negative"),
            models.CheckConstraint(condition=Q(paid_amount__gte=0), name="order_paid_non_negative"),
            models.CheckConstraint(condition=Q(paid_amount__lte=F("total_price")), name="order_paid_not_above_total"),
            models.CheckConstraint(condition=Q(start_date__isnull=True) | Q(deadline__isnull=True) | Q(deadline__gte=F("start_date")),
                                   name="order_deadline_after_start"),
        ]
        indexes = [
            models.Index(fields=["workshop", "status"], name="order_ws_status_idx"),
            models.Index(fields=["workshop", "-created_at"], name="order_ws_created_idx"),
            models.Index(fields=["workshop", "deadline"], name="order_ws_deadline_idx"),
            models.Index(fields=["workshop", "payment_status"], name="order_ws_payment_idx"),
            models.Index(fields=["assigned_employee"], name="order_assignee_idx"),
        ]

    def __str__(self):
        return self.order_number


class OrderStatusChange(models.Model):
    """Append-only status history of an order (the first row has an empty `from_status`)."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=14, blank=True)
    to_status = models.CharField(max_length=14)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["order", "created_at"], name="orderhist_order_idx")]


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In progress"
        REVIEW = "review", "Review"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    workshop = models.ForeignKey(Workshop, on_delete=models.PROTECT, related_name="tasks")
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(WorkshopMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    deadline = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["workshop", "status"], name="task_ws_status_idx"),
            models.Index(fields=["workshop", "deadline"], name="task_ws_deadline_idx"),
            models.Index(fields=["assigned_to", "status"], name="task_assignee_status_idx"),
            models.Index(fields=["order", "status"], name="task_order_status_idx"),
        ]

    def __str__(self):
        return self.title


class TaskStatusChange(models.Model):
    """Append-only status history of a task."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["task", "created_at"], name="taskhist_task_idx")]
