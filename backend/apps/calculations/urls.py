from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CalculationViewSet, MaterialCalculationView

router = SimpleRouter()
router.register("", CalculationViewSet, basename="calculation")
urlpatterns = [path("material/", MaterialCalculationView.as_view())] + router.urls
