from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import TemplateViewSet, categories

router = SimpleRouter()
router.register("templates", TemplateViewSet, basename="template")
urlpatterns = [path("categories/", categories)] + router.urls
