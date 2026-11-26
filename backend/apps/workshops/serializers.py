from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.core.signing import sign_file
from apps.projects.models import Project

from . import access, services
from .models import Order, OrderStatusChange, Task, TaskStatusChange, Workshop, WorkshopMember

MONEY_FIELDS = ("total_price", "paid_amount", "payment_status", "outstanding_amount")


class ScopedPK(serializers.PrimaryKeyRelatedField):
    """Primary-key field that can only point at objects the requesting user may see. An id that does not exist and an id that
    belongs to somebody else give the same error, so ids cannot be probed."""

    def __init__(self, model, scope, **kwargs):
        self._scope = scope
        super().__init__(queryset=model.objects.none(), **kwargs)

    def get_queryset(self):
        return self._scope(self.context["request"].user)


def _members_scope(user):
    return WorkshopMember.objects.filter(workshop_id__in=access.active_memberships(user).values("workshop_id"))


def _workshop_field(**kw):
    return ScopedPK(Workshop, access.visible_workshops, required=False, **kw)


def _person(user, *, with_email=False):
    if user is None:
        return None
    d = {"id": user.id, "full_name": user.full_name}
    if with_email:
        d["email"] = user.email
    return d


class OwnedIdsMixin:
    """`owned_workshop_ids` is computed once per request by the view (a set of workshop ids the user owns)."""

    def _owns(self, workshop_id) -> bool:
        return workshop_id in self.context.get("owned_workshop_ids", ())


# ------------------------------------------------------------------------------------------------ workshop
class WorkshopSerializer(OwnedIdsMixin, serializers.ModelSerializer):
    owner = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    my_role = serializers.SerializerMethodField()

    class Meta:
        model = Workshop
        fields = ["id", "name", "kind", "city", "slug", "description", "owner", "phone", "email", "address", "logo_url", "status", "review_note", "my_role",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "review_note", "created_at", "updated_at"]

    def get_owner(self, obj):
        return _person(obj.owner)

    def get_logo_url(self, obj):
        return f"/api/v1/workshops/{obj.pk}/logo-file/?sig={sign_file('workshop-logo', obj.pk)}" if obj.logo else None

    def get_my_role(self, obj):
        return self.context.get("my_roles", {}).get(obj.pk)

    def validate_status(self, v):
        if v not in (Workshop.Status.ACTIVE, Workshop.Status.INACTIVE):
            raise serializers.ValidationError("You can switch between active and inactive. Approval and suspension are done by platform administrators.")
        return v

    def validate_name(self, v):
        v = v.strip()
        if len(v) < 2:
            raise serializers.ValidationError("Enter at least 2 characters.")
        return v


class LogoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workshop
        fields = ["logo"]


# ------------------------------------------------------------------------------------------------ members
class MemberSerializer(OwnedIdsMixin, serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = WorkshopMember
        fields = ["id", "workshop", "user", "role", "status", "joined_at", "removed_at", "created_at", "updated_at"]
        read_only_fields = fields

    def get_user(self, obj):
        # contact details of colleagues are private: only the owner (and the person themself) sees the email
        me = self.context["request"].user
        return _person(obj.user, with_email=self._owns(obj.workshop_id) or obj.user_id == me.id)


class InviteSerializer(serializers.Serializer):
    email = serializers.EmailField()


class MemberUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=WorkshopMember.Role.choices, required=False)
    status = serializers.ChoiceField(choices=[WorkshopMember.Status.ACTIVE, WorkshopMember.Status.REMOVED], required=False)
    confirm_transfer = serializers.BooleanField(required=False, default=False)


class InvitationSerializer(serializers.ModelSerializer):
    workshop = serializers.SerializerMethodField()
    invited_by = serializers.SerializerMethodField()

    class Meta:
        model = WorkshopMember
        fields = ["id", "workshop", "invited_by", "role", "status", "created_at"]

    def get_workshop(self, obj):
        return {"id": obj.workshop_id, "name": obj.workshop.name}

    def get_invited_by(self, obj):
        return _person(obj.invited_by)


# ------------------------------------------------------------------------------------------------ orders
class OrderStatusChangeSerializer(serializers.ModelSerializer):
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model = OrderStatusChange
        fields = ["id", "from_status", "to_status", "changed_by", "note", "created_at"]

    def get_changed_by(self, obj):
        return _person(obj.changed_by)


class OrderSerializer(OwnedIdsMixin, serializers.ModelSerializer):
    outstanding_amount = serializers.SerializerMethodField()
    allowed_next_statuses = serializers.SerializerMethodField()
    assigned_employee_detail = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    status_note = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=255)
    # the workshop is chosen on creation and never changes afterwards
    workshop = _workshop_field()
    assigned_employee = ScopedPK(WorkshopMember, _members_scope, required=False, allow_null=True)
    related_project = ScopedPK(Project, lambda u: Project.objects.filter(owner=u), required=False, allow_null=True)

    class Meta:
        model = Order
        fields = ["id", "order_number", "workshop", "customer_name", "customer_phone", "customer_email", "customer_address", "customer_user",
                  "title", "description", "related_project", "project", "total_price", "paid_amount", "outstanding_amount", "payment_status",
                  "status", "status_note", "allowed_next_statuses", "assigned_employee", "assigned_employee_detail", "start_date", "deadline", "completed_at",
                  "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "order_number", "completed_at", "created_by", "created_at", "updated_at", "customer_user"]
        extra_kwargs = {"payment_status": {"required": False}, "status": {"required": False}}

    def get_outstanding_amount(self, obj):
        if obj.status == Order.Status.CANCELLED or obj.payment_status == Order.PaymentStatus.REFUNDED:
            return "0.00"
        return str(obj.total_price - obj.paid_amount)

    def get_allowed_next_statuses(self, obj):
        return services.allowed_order_statuses(obj, self._owns(obj.workshop_id))

    def get_assigned_employee_detail(self, obj):
        m = obj.assigned_employee
        return {"id": m.id, **_person(m.user), "status": m.status} if m else None

    def get_project(self, obj):
        p = obj.related_project
        return {"id": p.id, "name": p.name} if p else None

    def validate(self, attrs):
        if self.instance is not None and "workshop" in attrs and attrs["workshop"].pk != self.instance.workshop_id:
            raise serializers.ValidationError({"workshop": "An order cannot be moved to another workshop."})
        return attrs

    def validate_total_price(self, v):
        if v < 0:
            raise serializers.ValidationError("Cannot be negative.")
        return v

    def validate_paid_amount(self, v):
        if v < 0:
            raise serializers.ValidationError("Cannot be negative.")
        return v

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._owns(instance.workshop_id):  # employees never see money fields
            for f in MONEY_FIELDS:
                data.pop(f, None)
            data.pop("customer_user", None)
        return data


class OrderDetailSerializer(OrderSerializer):
    status_history = OrderStatusChangeSerializer(many=True, read_only=True)
    tasks_count = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ["status_history", "tasks_count"]

    def get_tasks_count(self, obj):
        return len(obj.tasks.all())  # served from the prefetch


# ------------------------------------------------------------------------------------------------ tasks
class TaskStatusChangeSerializer(serializers.ModelSerializer):
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model = TaskStatusChange
        fields = ["id", "from_status", "to_status", "changed_by", "note", "created_at"]

    def get_changed_by(self, obj):
        return _person(obj.changed_by)


class TaskSerializer(serializers.ModelSerializer):
    assigned_to_detail = serializers.SerializerMethodField()
    order_number = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    allowed_next_statuses = serializers.SerializerMethodField()
    status_note = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=255)
    workshop = _workshop_field()
    order = ScopedPK(Order, access.visible_orders, required=False, allow_null=True)
    assigned_to = ScopedPK(WorkshopMember, _members_scope, required=False, allow_null=True)

    class Meta:
        model = Task
        fields = ["id", "workshop", "order", "order_number", "title", "description", "assigned_to", "assigned_to_detail", "created_by", "priority",
                  "status", "status_note", "allowed_next_statuses", "deadline", "is_overdue", "started_at", "completed_at", "created_at", "updated_at"]
        read_only_fields = ["id", "created_by", "started_at", "completed_at", "created_at", "updated_at"]
        extra_kwargs = {"status": {"required": False}}

    def validate(self, attrs):
        if self.instance is not None:
            if "workshop" in attrs and attrs["workshop"].pk != self.instance.workshop_id:
                raise serializers.ValidationError({"workshop": "A task cannot be moved to another workshop."})
            if "order" in attrs and (attrs["order"].pk if attrs["order"] else None) != self.instance.order_id:
                raise serializers.ValidationError({"order": "A task cannot be moved to another order."})
        return attrs

    def get_assigned_to_detail(self, obj):
        m = obj.assigned_to
        return {"id": m.id, **_person(m.user), "status": m.status} if m else None

    def get_order_number(self, obj):
        return obj.order.order_number if obj.order_id else None

    def get_allowed_next_statuses(self, obj):
        ctx = self.context
        owner = obj.workshop_id in ctx.get("owned_workshop_ids", ())
        mine = ctx.get("my_member_ids", ())
        return services.allowed_task_statuses(obj, is_owner=owner, is_assignee=obj.assigned_to_id in mine)

    def get_is_overdue(self, obj):
        return bool(obj.deadline and obj.deadline < timezone.now() and obj.status in ("pending", "in_progress", "review"))


class TaskDetailSerializer(TaskSerializer):
    status_history = TaskStatusChangeSerializer(many=True, read_only=True)

    class Meta(TaskSerializer.Meta):
        fields = TaskSerializer.Meta.fields + ["status_history"]
