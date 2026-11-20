from django.urls import path

from . import views

urlpatterns = [path("me/", views.MyAnalyticsView.as_view()), path("features/", views.FeaturesView.as_view())]
