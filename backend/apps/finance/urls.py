from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CommissionView, PaymentViewSet, SummaryView

router = SimpleRouter()
router.register("payments", PaymentViewSet, basename="finance-payment")
urlpatterns = [path("commission/", CommissionView.as_view()), path("summary/", SummaryView.as_view())] + router.urls
