from django.urls import path

from . import bot_views as v

urlpatterns = [
    path("", v.BotRoomFlowStartView.as_view()),
    path("<int:pk>/", v.BotRoomFlowDetailView.as_view()),
    path("<int:pk>/answer/", v.BotRoomFlowAnswerView.as_view()),
    path("<int:pk>/back/", v.BotRoomFlowBackView.as_view()),
    path("<int:pk>/abandon/", v.BotRoomFlowAbandonView.as_view()),
    path("<int:pk>/model/", v.BotRoomFlowModelView.as_view()),
    path("<int:pk>/photo/", v.BotRoomFlowPhotoView.as_view()),
    path("<int:pk>/items/", v.BotRoomFlowItemsView.as_view()),
    path("<int:pk>/items/<str:item_id>/", v.BotRoomFlowItemDetailView.as_view()),
]
