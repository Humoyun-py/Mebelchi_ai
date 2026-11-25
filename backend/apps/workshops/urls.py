from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register(r"workshops/(?P<workshop_pk>[0-9]+)/members", views.MemberViewSet, basename="workshop-member")
router.register("workshop-invitations", views.InvitationListView, basename="workshop-invitation")
router.register("workshops", views.WorkshopViewSet, basename="workshop")
router.register("orders", views.OrderViewSet, basename="order")
router.register("tasks", views.TaskViewSet, basename="task")

urlpatterns = [path("workshops/me/", views.WorkshopMeView.as_view()),
               path("workshops/<int:pk>/logo-file/", views.WorkshopLogoFileView.as_view())] + router.urls
