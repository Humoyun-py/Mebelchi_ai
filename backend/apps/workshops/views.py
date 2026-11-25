from django.http import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.filters import SearchFilter
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.signing import verify_file

from . import access, services
from .filters import OrderFilter, TaskFilter
from .models import Order, Task, Workshop, WorkshopMember
from .ordering import NullsLastOrderingFilter
from .serializers import (InvitationSerializer, InviteSerializer, LogoSerializer, MemberSerializer, MemberUpdateSerializer, OrderDetailSerializer,
                          OrderSerializer, TaskDetailSerializer, TaskSerializer, WorkshopSerializer)

M = WorkshopMember


class ConflictMixin:
    """Business-rule conflicts (e.g. deleting a record that must be kept) are answered with 409."""

    def handle_exception(self, exc):
        if isinstance(exc, services.ConflictError):
            from rest_framework.exceptions import APIException

            class Conflict(APIException):
                status_code = 409
                default_detail = str(exc)
            exc = Conflict(str(exc))
        return super().handle_exception(exc)


class RequestScopeMixin:
    """Per-request context shared by the serializers: which workshops the user owns / belongs to (two small queries, once)."""

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        user = self.request.user
        if user.is_authenticated and "my_roles" not in ctx:
            rows = list(access.active_memberships(user).values_list("workshop_id", "role", "id"))
            ctx["my_roles"] = {w: r for w, r, _ in rows}
            ctx["owned_workshop_ids"] = {w for w, r, _ in rows if r == M.Role.OWNER}
            ctx["my_member_ids"] = {i for _, _, i in rows}
        return ctx

    def owned_ids(self) -> set:
        return self.get_serializer_context().get("owned_workshop_ids", set())


def _require_workshop_param(serializer):
    ws = serializer.validated_data.get("workshop")
    if ws is None:
        raise ValidationError({"workshop": "This field is required."})
    return ws


def _only_owned_workshop_filter(view, *params):
    """Sorting/filtering by money fields would leak relative order values to employees; allow it only inside an owned workshop."""
    q = view.request.query_params
    used = [p for p in params if p in q.get("ordering", "") or p in q]
    roles = view.get_serializer_context().get("my_roles", {})
    employee_somewhere = any(r != M.Role.OWNER for r in roles.values())
    if used and employee_somewhere and str(q.get("workshop", "")) not in {str(i) for i in view.owned_ids()}:
        raise ValidationError({"detail": f"Filtering or sorting by {', '.join(used)} requires the workshop filter of a workshop you own."})


# ------------------------------------------------------------------------------------------------ workshops
class WorkshopViewSet(ConflictMixin, RequestScopeMixin, viewsets.ModelViewSet):
    queryset = Workshop.objects.none()  # real scoping happens in get_queryset(); this lets the schema generator see the model
    serializer_class = WorkshopSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status"]
    search_fields = ["name", "slug", "description"]
    ordering_fields = ["name", "created_at", "status"]

    def get_queryset(self):
        return access.visible_workshops(self.request.user).select_related("owner")

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        ws = services.create_workshop(request.user, dict(s.validated_data))
        ctx = {**self.get_serializer_context(), "my_roles": {ws.pk: M.Role.OWNER}}
        return Response(WorkshopSerializer(ws, context=ctx).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        ws = self.get_object()
        s = self.get_serializer(ws, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        ws = services.update_workshop(ws, request.user, dict(s.validated_data))
        return Response(self.get_serializer(ws).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_workshop(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"])
    def statistics(self, request, pk=None):
        ws = self.get_object()
        access.require_owner(request.user, ws)
        return Response(services.workshop_statistics(ws))

    @extend_schema(request=LogoSerializer, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post", "delete"], url_path="logo")
    def logo(self, request, pk=None):
        ws = self.get_object()
        access.require_owner(request.user, ws)
        access.require_writable(ws)
        if request.method == "DELETE":
            ws.logo.delete(save=True)
        else:
            s = LogoSerializer(ws, data=request.data)
            s.is_valid(raise_exception=True)
            s.save()
        return Response(self.get_serializer(Workshop.objects.select_related("owner").get(pk=ws.pk)).data)


class WorkshopLogoFileView(APIView):
    """Public but bound to one workshop by a short-lived signature (so <img> works without headers)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=OpenApiTypes.BINARY)
    def get(self, request, pk):
        if not verify_file(request.query_params.get("sig", ""), "workshop-logo", pk):
            raise Http404
        ws = Workshop.objects.filter(pk=pk).exclude(logo="").first()
        if not ws:
            raise Http404
        return FileResponse(ws.logo.open("rb"))


# ------------------------------------------------------------------------------------------------ members
class MemberViewSet(ConflictMixin, RequestScopeMixin, mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
                    mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """/workshops/{workshop_pk}/members/. Owners invite and remove; every member sees the (name-only) roster; an invited
    person answers their own invitation by PATCHing their member row with status=active (accept) or status=removed (decline/leave)."""

    queryset = M.objects.none()
    serializer_class = MemberSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    ordering_fields = ["created_at", "role", "status"]
    filterset_fields = ["role", "status"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.workshop = Workshop.objects.select_related("owner").filter(pk=kwargs["workshop_pk"]).first()
        # the workshop does not exist for people who have nothing to do with it
        if not self.workshop or not M.objects.filter(workshop=self.workshop, user=request.user).exists():
            raise NotFound()

    def get_queryset(self):
        qs = M.objects.filter(workshop=self.workshop).select_related("user", "workshop")
        me = self.request.user
        if access.is_owner(me, self.workshop.pk):
            return qs
        if self.action == "list":  # colleagues see the active roster (names only)
            if access.membership(me, self.workshop.pk) is None:
                raise NotFound()
            return qs.filter(status=M.Status.ACTIVE)
        return qs.filter(user=me)  # detail routes: only your own row, whatever its status

    @extend_schema(request=InviteSerializer, responses=MemberSerializer)
    def create(self, request, *args, **kwargs):
        s = InviteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        m = services.invite_member(self.workshop, request.user, s.validated_data["email"])
        return Response(self.get_serializer(m).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=MemberUpdateSerializer, responses=MemberSerializer)
    def partial_update(self, request, *args, **kwargs):
        m = self.get_object()
        s = MemberUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if not d.get("role") and not d.get("status"):
            raise ValidationError({"detail": "Send role or status."})
        me = request.user
        if d.get("role"):
            access.require_owner(me, self.workshop)
            if d["role"] == m.role:
                pass
            elif d["role"] == M.Role.OWNER:
                if not d["confirm_transfer"]:
                    raise ValidationError({"confirm_transfer": "Transferring ownership makes this person the owner and you an employee. Send confirm_transfer=true to confirm."})
                m = services.transfer_ownership(self.workshop, me, m)
            else:
                raise ValidationError({"role": "The owner role cannot be taken away directly. Transfer ownership to another employee instead."})
        if d.get("status"):
            if m.user_id != me.id:
                raise PermissionDenied("Only the person themself can accept or decline an invitation or leave the workshop. Owners remove members with DELETE.")
            if d["status"] == M.Status.ACTIVE:
                m = services.accept_invitation(m, me)
            elif m.status == M.Status.INVITED:
                m = services.remove_member(m, me, event="member.declined")
            else:
                m = services.remove_member(m, me, event="member.left")
        return Response(self.get_serializer(m).data)

    def destroy(self, request, *args, **kwargs):
        m = self.get_object()
        access.require_owner(request.user, self.workshop)
        services.remove_member(m, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationListView(RequestScopeMixin, viewsets.GenericViewSet, mixins.ListModelMixin):
    """My pending invitations to join workshops."""

    queryset = M.objects.none()
    serializer_class = InvitationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return M.objects.filter(user=self.request.user, status=M.Status.INVITED).select_related("workshop", "invited_by").order_by("-created_at")


# ------------------------------------------------------------------------------------------------ orders
class OrderViewSet(ConflictMixin, RequestScopeMixin, viewsets.ModelViewSet):
    queryset = Order.objects.none()  # real scoping happens in get_queryset(); this lets the schema generator see the model
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, NullsLastOrderingFilter]
    filterset_class = OrderFilter
    search_fields = ["order_number", "title", "customer_name", "customer_phone"]
    ordering_fields = ["created_at", "updated_at", "deadline", "status", "order_number", "total_price"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        return OrderDetailSerializer if self.action == "retrieve" else OrderSerializer

    def get_queryset(self):
        qs = access.visible_orders(self.request.user).select_related("workshop", "assigned_employee__user", "related_project")
        if self.action == "retrieve":
            qs = qs.prefetch_related("status_history__changed_by", "tasks")
        return qs

    def filter_queryset(self, queryset):
        if self.action == "list":
            _only_owned_workshop_filter(self, "total_price", "payment_status")
        return super().filter_queryset(queryset)

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        ws = data.pop("workshop", None) or _require_workshop_param(s)
        order = services.create_order(ws, request.user, data)
        return Response(self.get_serializer(self._fresh(order)).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        s = self.get_serializer(order, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        data.pop("workshop", None)
        order = services.update_order(order, request.user, data)
        return Response(OrderDetailSerializer(self._fresh(order, detail=True), context=self.get_serializer_context()).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_order(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _fresh(self, order, detail=False):
        qs = Order.objects.select_related("workshop", "assigned_employee__user", "related_project")
        if detail:
            qs = qs.prefetch_related("status_history__changed_by", "tasks")
        return qs.get(pk=order.pk)


# ------------------------------------------------------------------------------------------------ tasks
class TaskViewSet(ConflictMixin, RequestScopeMixin, viewsets.ModelViewSet):
    queryset = Task.objects.none()  # real scoping happens in get_queryset(); this lets the schema generator see the model
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, NullsLastOrderingFilter]
    filterset_class = TaskFilter
    search_fields = ["title", "description", "order__order_number"]
    ordering_fields = ["created_at", "updated_at", "deadline", "priority", "status"]
    ordering = ["-created_at", "-id"]

    def get_serializer_class(self):
        return TaskDetailSerializer if self.action == "retrieve" else TaskSerializer

    def get_queryset(self):
        qs = access.visible_tasks(self.request.user).select_related("workshop", "assigned_to__user", "order")
        if self.action == "retrieve":
            qs = qs.prefetch_related("status_history__changed_by")
        return qs

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        order = data.get("order")
        ws = data.pop("workshop", None)
        if order is not None:
            if ws is not None and ws.pk != order.workshop_id:
                raise ValidationError({"workshop": "This order belongs to a different workshop."})
            ws = order.workshop
        if ws is None:
            raise ValidationError({"workshop": "This field is required when the task has no order."})
        task = services.create_task(ws, request.user, data)
        return Response(self.get_serializer(self._fresh(task)).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        task = self.get_object()
        s = self.get_serializer(task, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        data = dict(s.validated_data)
        data.pop("workshop", None)
        data.pop("order", None)
        task = services.update_task(task, request.user, data)
        return Response(TaskDetailSerializer(self._fresh(task, detail=True), context=self.get_serializer_context()).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_task(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _fresh(self, task, detail=False):
        qs = Task.objects.select_related("workshop", "assigned_to__user", "order")
        if detail:
            qs = qs.prefetch_related("status_history__changed_by")
        return qs.get(pk=task.pk)
