from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.WorkshopMeView.as_view()),
]
