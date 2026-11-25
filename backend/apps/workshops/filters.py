import django_filters as f
from django.db.models import Q
from django.utils import timezone

from .models import Order, Task, WorkshopMember


class OrderFilter(f.FilterSet):
    deadline_after = f.DateFilter(field_name="deadline", lookup_expr="gte")
    deadline_before = f.DateFilter(field_name="deadline", lookup_expr="lte")
    created_after = f.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = f.DateFilter(field_name="created_at", lookup_expr="date__lte")
    overdue = f.BooleanFilter(method="filter_overdue", help_text="deadline passed and the order is not delivered or cancelled")
    mine = f.BooleanFilter(method="filter_mine", help_text="assigned to me")

    class Meta:
        model = Order
        fields = ["workshop", "status", "payment_status", "assigned_employee"]

    def filter_overdue(self, qs, name, value):
        late = Q(deadline__lt=timezone.localdate()) & ~Q(status__in=["delivered", "cancelled"])
        return qs.filter(late) if value else qs.exclude(late)

    def filter_mine(self, qs, name, value):
        mine = Q(assigned_employee__user=self.request.user, assigned_employee__status=WorkshopMember.Status.ACTIVE)
        return qs.filter(mine) if value else qs.exclude(mine)


class TaskFilter(f.FilterSet):
    deadline_after = f.IsoDateTimeFilter(field_name="deadline", lookup_expr="gte")
    deadline_before = f.IsoDateTimeFilter(field_name="deadline", lookup_expr="lte")
    overdue = f.BooleanFilter(method="filter_overdue", help_text="deadline passed and the task is still open")
    mine = f.BooleanFilter(method="filter_mine", help_text="assigned to me")
    employee = f.NumberFilter(field_name="assigned_to", help_text="alias of assigned_to (a member id)")

    class Meta:
        model = Task
        fields = ["workshop", "order", "assigned_to", "status", "priority"]

    def filter_overdue(self, qs, name, value):
        late = Q(deadline__lt=timezone.now(), status__in=["pending", "in_progress", "review"])
        return qs.filter(late) if value else qs.exclude(late)

    def filter_mine(self, qs, name, value):
        mine = Q(assigned_to__user=self.request.user, assigned_to__status=WorkshopMember.Status.ACTIVE)
        return qs.filter(mine) if value else qs.exclude(mine)
