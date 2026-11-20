from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import GalleryFileView, GalleryViewSet

router = SimpleRouter()
router.register("gallery", GalleryViewSet, basename="gallery")
urlpatterns = [path("gallery/<int:pk>/file/", GalleryFileView.as_view())] + router.urls
