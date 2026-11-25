from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.services import track
from apps.projects.models import Project

from . import engine
from .pricing import catalog_board_prices
from .models import Calculation
from .serializers import CabinetInputSerializer, CalculationSerializer


def run_engine(data: dict, prices: dict | None = None) -> dict:
    try:
        return engine.calculate(data, prices)
    except engine.EngineValidationError as e:
        raise ValidationError(e.errors)


class MaterialCalculationView(APIView):
    """Stateless calculation; with save=true the result is stored as a Calculation."""

    @extend_schema(request=CabinetInputSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        s = CabinetInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = dict(s.validated_data)
        save, name, project_id = d.pop("save"), d.pop("name", None), d.pop("project", None)
        prices, use_catalog = d.pop("prices", None), d.pop("use_catalog_prices", False)
        if use_catalog:
            prices = dict(prices or {})
            prices["board_price_per_m2"] = {**catalog_board_prices(request.user), **(prices.get("board_price_per_m2") or {})}
        result = run_engine(d, dict(prices) if prices is not None else None)
        track(request.user, "calculation", area=result["summary"]["total_area_m2"])
        if save:
            project = None
            if project_id:
                project = Project.objects.filter(pk=project_id, owner=request.user).first()
                if not project:
                    raise ValidationError({"project": "Project not found."})
            calc = Calculation.objects.create(owner=request.user, project=project, name=name or "Cabinet calculation",
                                              inputs=result["input"], result=result)
            result["saved_id"] = calc.id
        return Response(result)


class CalculationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = CalculationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project", "kind"]
    search_fields = ["name"]

    def get_queryset(self):
        return Calculation.objects.filter(owner=self.request.user)
