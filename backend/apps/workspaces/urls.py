from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import FolderViewSet, WorkspaceSummaryView

router = SimpleRouter()
router.register("folders", FolderViewSet, basename="folder")
urlpatterns = [path("workspace/summary/", WorkspaceSummaryView.as_view())] + router.urls
