from rest_framework.routers import SimpleRouter

from .views import CuttingListViewSet

router = SimpleRouter()
router.register("", CuttingListViewSet, basename="cutting-list")
urlpatterns = router.urls
