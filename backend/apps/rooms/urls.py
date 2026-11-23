from rest_framework.routers import SimpleRouter

from .views import RoomFlowViewSet

router = SimpleRouter()
router.register("room-flows", RoomFlowViewSet, basename="room-flow")
urlpatterns = router.urls
