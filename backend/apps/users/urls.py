from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.MeView.as_view()),
    path("me/role/", views.RoleView.as_view()),
    path("me/avatar/", views.AvatarView.as_view()),
    path("me/password/", views.PasswordChangeView.as_view()),
    path("me/sessions/", views.SessionsView.as_view()),
    path("me/sessions/<int:pk>/", views.SessionDetailView.as_view()),
    path("me/storage/", views.StorageView.as_view()),
    path("<int:pk>/avatar/", views.AvatarFileView.as_view()),
]
