from django.http import HttpResponse
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.analytics.services import track
from apps.calculations import engine
from apps.core.throttles import ExportRateThrottle
from apps.core.views import OwnedModelViewSet
from apps.projects.models import Project
from apps.subscriptions.services import enforce_export_limit

from . import exports, services
from .models import CuttingList
from .serializers import (CuttingListSerializer, FromCalculationSerializer, OptimizationRunSerializer, OptimizeParamsSerializer)


class CuttingListViewSet(OwnedModelViewSet):
    queryset = CuttingList.objects.prefetch_related("parts", "runs")
    serializer_class = CuttingListSerializer
    filterset_fields = ["project"]
    search_fields = ["name"]

    @action(detail=False, methods=["post"], url_path="from-calculation")
    def from_calculation(self, request):
        s = FromCalculationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = dict(s.validated_data)
        name, project_id = d.pop("name", None), d.pop("project", None)
        length, width = d.pop("sheet_length", 2800), d.pop("sheet_width", 2070)
        try:
            calc = engine.calculate(d)
        except engine.EngineValidationError as e:
            raise ValidationError(e.errors)
        project = None
        if project_id:
            project = Project.objects.filter(pk=project_id, owner=request.user).first()
            if not project:
                raise ValidationError({"project": "Project not found."})
        cl = services.create_from_calculation(request.user, calc, project=project, name=name, sheet_length=length, sheet_width=width)
        track(request.user, "cutting_list_generated")
        return Response(self.get_serializer(cl).data, status=201)

    @action(detail=True, methods=["post"])
    def optimize(self, request, pk=None):
        p = OptimizeParamsSerializer(data=request.data)
        p.is_valid(raise_exception=True)
        run = services.run_optimization(self.get_object(), p.validated_data["allow_rotation"])
        track(request.user, "optimization", sheets=run.sheet_count, utilization=run.utilization_pct)
        return Response(OptimizationRunSerializer(run).data, status=201)

    @action(detail=True, methods=["get"])
    def runs(self, request, pk=None):
        return Response(OptimizationRunSerializer(self.get_object().runs.all()[:10], many=True).data)

    def _export(self, request, kind):
        enforce_export_limit(request.user)
        cl = self.get_object()
        run = cl.runs.first()
        track(request.user, f"export_{kind}", cutting_list=cl.pk)
        if kind == "pdf":
            data, ctype = exports.to_pdf(cl, run), "application/pdf"
        else:
            data, ctype = exports.to_xlsx(cl, run), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in cl.name)[:60] or "cutting-list"
        resp = HttpResponse(data, content_type=ctype)
        resp["Content-Disposition"] = f'attachment; filename="{safe}.{kind}"'
        return resp

    @action(detail=True, methods=["get"], url_path="export/pdf", throttle_classes=[ExportRateThrottle])
    def export_pdf(self, request, pk=None):
        return self._export(request, "pdf")

    @action(detail=True, methods=["get"], url_path="export/xlsx", throttle_classes=[ExportRateThrottle])
    def export_xlsx(self, request, pk=None):
        return self._export(request, "xlsx")
