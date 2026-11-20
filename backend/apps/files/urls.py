from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import FileDownloadView, UserFileViewSet

router = SimpleRouter()
router.register("files", UserFileViewSet, basename="file")
urlpatterns = [path("files/<int:pk>/download/", FileDownloadView.as_view())] + router.urls
