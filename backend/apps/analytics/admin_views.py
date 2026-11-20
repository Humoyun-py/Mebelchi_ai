from datetime import timedelta

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsPlatformAdmin
from apps.notifications.services import notify
from apps.projects.models import Project
from apps.subscriptions import services as sub_services
from apps.subscriptions.models import Payment, Plan, Subscription

from .models import FeatureFlag, SystemLog, UsageEvent

User = get_user_model()


class AdminBase:
    permission_classes = [IsPlatformAdmin]


class StatsView(AdminBase, APIView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        from apps.files.models import UserFile
        from apps.galleries.models import GalleryImage
        now = timezone.now()
        since = now - timedelta(days=14)
        signups = (User.objects.filter(date_joined__gte=since).annotate(d=TruncDate("date_joined")).values("d").annotate(n=Count("id")).order_by("d"))
        usage = UsageEvent.objects.filter(created_at__gte=since).values("kind").annotate(n=Count("id")).order_by("-n")[:12]
        storage = (GalleryImage.objects.aggregate(s=Sum("size_bytes"))["s"] or 0) + (UserFile.objects.aggregate(s=Sum("size_bytes"))["s"] or 0)
        return Response({
            "users": {"total": User.objects.count(), "active_30d": User.objects.filter(last_login__gte=now - timedelta(days=30)).count(),
                      "by_role": list(User.objects.values("role").annotate(n=Count("id")))},
            "projects": {"total": Project.objects.count(), "active": Project.objects.filter(status="active").count()},
            "subscriptions": list(Subscription.objects.values("plan__name").annotate(n=Count("id"))),
            "payments": {"pending": Payment.objects.filter(status="pending").count(), "paid": Payment.objects.filter(status="paid").count(),
                         "revenue_usd": str(Payment.objects.filter(status="paid").aggregate(s=Sum("amount"))["s"] or 0)},
            "storage_bytes": storage,
            "signups_14d": [{"date": s["d"].isoformat(), "count": s["n"]} for s in signups],
            "usage_14d": list(usage),
            "errors_24h": SystemLog.objects.filter(created_at__gte=now - timedelta(hours=24)).count(),
        })


class AdminUserSerializer(serializers.ModelSerializer):
    plan = serializers.SerializerMethodField()
    project_count = serializers.IntegerField(source="projects.count", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "is_active", "is_staff", "date_joined", "last_login", "plan", "project_count"]
        read_only_fields = ["id", "email", "first_name", "last_name", "date_joined", "last_login", "plan", "project_count"]

    def get_plan(self, u):
        s = Subscription.objects.filter(user=u).select_related("plan").first()
        return s.plan.name if s else "Free"


class UserAdminViewSet(AdminBase, viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("-date_joined")
    serializer_class = AdminUserSerializer
    search_fields = ["email", "first_name", "last_name"]
    filterset_fields = ["role", "is_active", "is_staff"]
    http_method_names = ["get", "patch", "head", "options"]

    def perform_update(self, serializer):
        u = serializer.instance
        if u.pk == self.request.user.pk and (serializer.validated_data.get("is_active") is False or serializer.validated_data.get("is_staff") is False):
            raise ValidationError({"detail": "You cannot remove your own admin access or deactivate yourself."})
        if "is_staff" in serializer.validated_data and not self.request.user.is_superuser:
            raise ValidationError({"is_staff": "Only superusers can change admin status."})
        serializer.save()


class AdminProjectSerializer(serializers.ModelSerializer):
    owner_email = serializers.CharField(source="owner.email", read_only=True)

    class Meta:
        model = Project
        fields = ["id", "name", "category", "status", "owner_email", "created_at", "updated_at"]


class ProjectAdminViewSet(AdminBase, viewsets.ReadOnlyModelViewSet):
    queryset = Project.objects.select_related("owner").order_by("-updated_at")
    serializer_class = AdminProjectSerializer
    search_fields = ["name", "owner__email"]
    filterset_fields = ["status", "category"]


class AdminSubscriptionSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source="user.email", read_only=True)
    plan_slug = serializers.SlugRelatedField(source="plan", slug_field="slug", queryset=Plan.objects.all())
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = Subscription
        fields = ["id", "email", "plan_slug", "plan_name", "status", "started_at"]
        read_only_fields = ["id", "started_at"]


class SubscriptionAdminViewSet(AdminBase, viewsets.ModelViewSet):
    queryset = Subscription.objects.select_related("user", "plan").order_by("-started_at")
    serializer_class = AdminSubscriptionSerializer
    search_fields = ["user__email"]
    filterset_fields = ["status", "plan__slug"]
    http_method_names = ["get", "patch", "head", "options"]


class AdminPaymentSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source="user.email", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "email", "plan_name", "amount", "currency", "status", "reference", "created_at", "confirmed_at"]
        read_only_fields = fields


class PaymentAdminViewSet(AdminBase, viewsets.ReadOnlyModelViewSet):
    queryset = Payment.objects.select_related("user", "plan")
    serializer_class = AdminPaymentSerializer
    filterset_fields = ["status"]
    search_fields = ["user__email", "reference"]

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        p = self.get_object()
        if p.status != Payment.Status.PENDING:
            raise ValidationError({"detail": "Only pending payments can be confirmed."})
        sub_services.confirm_payment(p)
        notify(p.user, f"{p.plan.name} plan activated", "Your payment was confirmed.", "success")
        return Response(self.get_serializer(p).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        p = self.get_object()
        if p.status != Payment.Status.PENDING:
            raise ValidationError({"detail": "Only pending payments can be rejected."})
        p.status = Payment.Status.REJECTED
        p.save(update_fields=["status"])
        return Response(self.get_serializer(p).data)


class LogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemLog
        fields = ["id", "level", "message", "path", "status_code", "created_at"]


class LogAdminViewSet(AdminBase, viewsets.ReadOnlyModelViewSet):
    queryset = SystemLog.objects.all()
    serializer_class = LogSerializer
    filterset_fields = ["level", "status_code"]
    search_fields = ["message", "path"]


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = ["id", "key", "description", "enabled"]


class FeatureAdminViewSet(AdminBase, viewsets.ModelViewSet):
    queryset = FeatureFlag.objects.all()
    serializer_class = FeatureSerializer
    pagination_class = None


class BroadcastView(AdminBase, APIView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        title, body = (request.data.get("title") or "").strip(), (request.data.get("body") or "").strip()
        if not title or len(title) > 160:
            raise ValidationError({"title": "Required, max 160 characters."})
        n = 0
        for u in User.objects.filter(is_active=True, notify_system=True).iterator():
            notify(u, title, body)
            n += 1
        return Response({"sent": n})


class StorageAdminView(AdminBase, APIView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        from apps.galleries.models import GalleryImage
        rows = (GalleryImage.objects.values("owner__email").annotate(bytes=Sum("size_bytes"), images=Count("id")).order_by("-bytes")[:20])
        return Response([{"email": r["owner__email"], "image_bytes": r["bytes"] or 0, "images": r["images"]} for r in rows])
