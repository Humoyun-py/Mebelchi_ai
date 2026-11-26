from rest_framework.routers import SimpleRouter

from .views import RoomFlowViewSet

router = SimpleRouter()
router.register("rooms", RoomFlowViewSet, basename="room")
urlpatterns = router.urls
