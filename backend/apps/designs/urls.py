from rest_framework.routers import SimpleRouter

from .views import DesignViewSet

router = SimpleRouter()
router.register("designs", DesignViewSet, basename="design")
urlpatterns = router.urls
