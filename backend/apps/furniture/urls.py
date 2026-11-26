from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import ImageFileView, TemplateViewSet, categories

router = SimpleRouter()
router.register("templates", TemplateViewSet, basename="template")
urlpatterns = [path("categories/", categories), path("images/<int:pk>/file/", ImageFileView.as_view())] + router.urls
