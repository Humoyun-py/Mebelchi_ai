from django.urls import path

from .views import AndroidDownloadView, AndroidReleasesView

urlpatterns = [
    path("android/", AndroidReleasesView.as_view()),
    path("android/latest/download/", AndroidDownloadView.as_view()),
    path("android/<int:code>/download/", AndroidDownloadView.as_view()),
]
