from django.urls import path

from . import views as v

urlpatterns = [
    # web account (JWT)
    path("link-code/", v.LinkCodeView.as_view()),
    path("status/", v.LinkStatusView.as_view()),
    # bot (X-Bot-Secret), always acting on behalf of a linked account
    path("bot/link/", v.BotLinkView.as_view()),
    path("bot/me/", v.BotMeView.as_view()),
    path("bot/unlink/", v.BotUnlinkView.as_view()),
    path("bot/projects/", v.BotProjectsView.as_view()),
    path("bot/projects/<int:pk>/", v.BotProjectDetailView.as_view()),
    path("bot/calculate/", v.BotCalculateView.as_view()),
    path("bot/cutting-lists/", v.BotCuttingListView.as_view()),
    path("bot/cutting-lists/<int:pk>/export/<str:kind>/", v.BotCuttingExportView.as_view()),
    path("bot/files/", v.BotFileUploadView.as_view()),
    path("bot/notifications/", v.BotNotificationsView.as_view()),
    path("bot/admin/stats/", v.BotAdminStatsView.as_view()),
    path("bot/admin/broadcast/", v.BotAdminBroadcastView.as_view()),
    path("bot/admin/system/", v.BotAdminSystemView.as_view()),
]
