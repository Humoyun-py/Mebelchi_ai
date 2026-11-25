import logging
import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.admin_views import _check_celery, _check_database, _check_redis
from apps.analytics.services import track
from apps.calculations import engine
from apps.core.validators import validate_document, validate_image
from apps.cutting_lists import exports, services as cl_services
from apps.cutting_lists.models import CuttingList
from apps.files.models import UserFile
from apps.files.serializers import KIND_BY_EXT
from apps.files.services import storage_summary
from apps.notifications.models import Notification
from apps.projects import services as project_services
from apps.projects.models import Project
from apps.subscriptions.services import enforce_export_limit, enforce_storage_limit

from . import services
from .models import TelegramLink
from .permissions import IsTelegramBot
from .serializers import (BotCalcSerializer, BotCuttingListSerializer, BotFileUploadSerializer, BotProjectCreateSerializer,
                          BotProjectRenameSerializer)
from .tasks import broadcast_to_telegram
from .throttles import TelegramUserThrottle

logger = logging.getLogger("mebelchi.telegram")
User = get_user_model()


class LinkFailed(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, code: str):
        self.detail = {"detail": code, "code": code}


class NotLinked(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "not_linked"

    def __init__(self):
        # Dict detail is returned as-is, so the bot can branch on "code" without parsing English text.
        self.detail = {"detail": "This Telegram account is not linked to a MEBELCHI AI account.", "code": self.default_code}


def user_summary(user) -> dict:
    return {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name,
            "role": user.role, "language": user.language, "is_staff": user.is_staff}


# ----- web (JWT) side -----------------------------------------------------------------------------------------------

class LinkCodeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        code, expires_at = services.create_link_code(request.user)
        return Response({"code": code, "expires_at": expires_at, "ttl_seconds": int(services.CODE_TTL.total_seconds())},
                        status=status.HTTP_201_CREATED)


class LinkStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request):
        link = TelegramLink.objects.filter(user=request.user).first()
        return Response({"linked": bool(link), "username": link.username if link else "",
                         "linked_at": link.linked_at if link else None})

    @extend_schema(request=None, responses={204: None})
    def delete(self, request):
        services.unlink_user(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ----- bot side (shared secret, acting on behalf of a linked user) -------------------------------------------------

class BotView(APIView):
    authentication_classes: list = []
    permission_classes = [IsTelegramBot]
    throttle_classes = [TelegramUserThrottle]

    def user_for(self, telegram_id):
        user = services.user_for_telegram(int(telegram_id))
        if user is None:
            raise NotLinked()
        return user

    def telegram_id_from(self, source):
        value = source.get("telegram_id")
        if value in (None, ""):
            raise ValidationError({"telegram_id": "Required."})
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValidationError({"telegram_id": "Must be an integer."})


class BotLinkView(BotView):
    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        telegram_id = self.telegram_id_from(request.data)
        try:
            user = services.link_telegram(telegram_id, str(request.data.get("username", "")), str(request.data.get("code", "")))
        except services.LinkError as e:
            raise LinkFailed(e.code)
        return Response({"linked": True, "user": user_summary(user)})


class BotMeView(BotView):
    def get(self, request):
        user = self.user_for(self.telegram_id_from(request.query_params))
        unread = Notification.objects.filter(user=user, read=False).count()
        return Response({"linked": True, "user": user_summary(user), "unread_notifications": unread})


class BotUnlinkView(BotView):
    def post(self, request):
        user = self.user_for(self.telegram_id_from(request.data))
        services.unlink_user(user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BotProjectsView(BotView):
    def get(self, request):
        user = self.user_for(self.telegram_id_from(request.query_params))
        qs = Project.objects.filter(owner=user, status=Project.Status.ACTIVE).order_by("-pinned", "-updated_at")[:20]
        return Response([{"id": p.id, "name": p.name, "category": p.category, "updated_at": p.updated_at} for p in qs])

    def post(self, request):
        s = BotProjectCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = self.user_for(s.validated_data["telegram_id"])
        project = Project.objects.create(owner=user, name=s.validated_data["name"], category=s.validated_data["category"])
        project_services.log(project, "created", "via Telegram")
        return Response({"id": project.id, "name": project.name, "category": project.category}, status=status.HTTP_201_CREATED)


class BotProjectDetailView(BotView):
    def patch(self, request, pk):
        s = BotProjectRenameSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = self.user_for(s.validated_data["telegram_id"])
        project = Project.objects.filter(pk=pk, owner=user).first()
        if project is None:
            raise NotFound()
        project.name = s.validated_data["name"]
        project.save(update_fields=["name", "updated_at"])
        project_services.log(project, "renamed", "via Telegram")
        return Response({"id": project.id, "name": project.name})


class BotCalculateView(BotView):
    def post(self, request):
        s = BotCalcSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = self.user_for(s.validated_data["telegram_id"])
        try:
            result = engine.calculate(s.calc_data())
        except engine.EngineValidationError as e:
            raise ValidationError(e.errors)
        track(user, "calculation", area=result["summary"]["total_area_m2"], source="telegram")
        return Response(result)


class BotCuttingListView(BotView):
    def post(self, request):
        s = BotCuttingListSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        vd = s.validated_data
        user = self.user_for(vd["telegram_id"])
        try:
            calc = engine.calculate(s.calc_data())
        except engine.EngineValidationError as e:
            raise ValidationError(e.errors)
        project = None
        if vd.get("project_id"):
            project = Project.objects.filter(pk=vd["project_id"], owner=user).first()
            if project is None:
                raise ValidationError({"project_id": "Project not found."})
        cl = cl_services.create_from_calculation(user, calc, project=project, name=vd.get("name") or None,
                                                 sheet_length=vd["sheet_length"], sheet_width=vd["sheet_width"])
        run = cl_services.run_optimization(cl)
        track(user, "cutting_list_generated", source="telegram")
        return Response({"id": cl.id, "name": cl.name, "parts_count": cl.parts.count(),
                         "sheet_count": run.sheet_count, "utilization_pct": run.utilization_pct,
                         "estimated_cost": run.result["summary"]["estimated_cost"],
                         "unplaced_count": run.result["summary"]["unplaced_count"],
                         "disclaimer": run.result["disclaimer"]}, status=status.HTTP_201_CREATED)


class BotCuttingExportView(BotView):
    def get(self, request, pk, kind):
        if kind not in ("pdf", "xlsx"):
            raise NotFound()
        user = self.user_for(self.telegram_id_from(request.query_params))
        enforce_export_limit(user)
        cl = CuttingList.objects.filter(pk=pk, owner=user).prefetch_related("parts", "runs").first()
        if cl is None:
            raise NotFound()
        run = cl.runs.first() or cl_services.run_optimization(cl)
        track(user, f"export_{kind}", cutting_list=cl.pk, source="telegram")
        if kind == "pdf":
            data, ctype = exports.to_pdf(cl, run), "application/pdf"
        else:
            data, ctype = exports.to_xlsx(cl, run), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in cl.name)[:60] or "cutting-list"
        resp = HttpResponse(data, content_type=ctype)
        resp["Content-Disposition"] = f'attachment; filename="{safe}.{kind}"'
        return resp


class BotFileUploadView(BotView):
    def post(self, request):
        s = BotFileUploadSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        vd = s.validated_data
        user = self.user_for(vd["telegram_id"])
        f = vd["file"]
        ext = os.path.splitext(f.name)[1].lower()
        # Validate content before anything is stored: the same validators as the web upload.
        try:
            if ext in (".jpg", ".jpeg", ".png", ".webp"):
                validate_image(f)
            else:
                validate_document(f)
        except DjangoValidationError as exc:
            raise ValidationError({"file": exc.messages})
        enforce_storage_limit(user, f.size)
        project = None
        if vd.get("project_id"):
            project = Project.objects.filter(pk=vd["project_id"], owner=user).first()
            if project is None:
                raise ValidationError({"project_id": "Project not found."})
        obj = UserFile.objects.create(owner=user, project=project, file=f, name=os.path.basename(f.name)[:200],
                                      kind=KIND_BY_EXT.get(ext, "other"), size_bytes=f.size)
        return Response({"id": obj.id, "name": obj.name, "kind": obj.kind, "size_bytes": obj.size_bytes,
                         "storage_percent": storage_summary(user)["percent"]}, status=status.HTTP_201_CREATED)


class BotNotificationsView(BotView):
    def get(self, request):
        user = self.user_for(self.telegram_id_from(request.query_params))
        qs = Notification.objects.filter(user=user, read=False).order_by("-created_at")[:5]
        return Response([{"id": n.id, "title": n.title, "body": n.body, "level": n.level, "created_at": n.created_at} for n in qs])


# ----- bot admin commands: the linked account must be staff -------------------------------------------------------

class BotAdminView(BotView):
    def staff_for(self, telegram_id):
        user = self.user_for(telegram_id)
        if not user.is_staff:
            raise PermissionDenied("Administrator rights required.")
        return user


class BotAdminStatsView(BotAdminView):
    def get(self, request):
        self.staff_for(self.telegram_id_from(request.query_params))
        return Response({
            "users_total": User.objects.count(),
            "users_active_30d": User.objects.filter(last_login__gte=timezone.now() - timedelta(days=30)).count(),
            "telegram_linked": TelegramLink.objects.count(),
            "projects_total": Project.objects.count(),
            "projects_by_category": list(Project.objects.values("category").annotate(n=Count("id")).order_by("-n")),
        })


class BotAdminBroadcastView(BotAdminView):
    def post(self, request):
        self.staff_for(self.telegram_id_from(request.data))
        text = str(request.data.get("text", "")).strip()
        if not text or len(text) > 2000:
            raise ValidationError({"text": "Required, max 2000 characters."})
        broadcast_to_telegram.delay(text)
        return Response({"queued": True}, status=status.HTTP_202_ACCEPTED)


class BotAdminSystemView(BotAdminView):
    def get(self, request):
        self.staff_for(self.telegram_id_from(request.query_params))
        return Response({"backend": {"status": "ok"}, "database": _check_database(),
                         "redis": _check_redis(), "celery": _check_celery()})

