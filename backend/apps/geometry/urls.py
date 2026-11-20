from django.urls import path

from . import views

urlpatterns = [path("preview/", views.PreviewView.as_view()), path("export/<str:fmt>/", views.ExportView.as_view())]
