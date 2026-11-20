from django.urls import path

from . import views

urlpatterns = [
    path("plans/", views.PlanListView.as_view()),
    path("me/", views.MySubscriptionView.as_view()),
    path("upgrade/", views.UpgradeView.as_view()),
]
