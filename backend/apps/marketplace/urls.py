from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CustomerOrderViewSet, MatchView

router = SimpleRouter()
router.register("orders", CustomerOrderViewSet, basename="marketplace-order")
urlpatterns = [path("match/", MatchView.as_view())] + router.urls
