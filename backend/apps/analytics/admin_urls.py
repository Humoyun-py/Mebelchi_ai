from django.urls import path
from rest_framework.routers import SimpleRouter

from . import admin_views as v

router = SimpleRouter()
router.register("users", v.UserAdminViewSet, basename="admin-user")
router.register("projects", v.ProjectAdminViewSet, basename="admin-project")
router.register("subscriptions", v.SubscriptionAdminViewSet, basename="admin-subscription")
router.register("payments", v.PaymentAdminViewSet, basename="admin-payment")
router.register("logs", v.LogAdminViewSet, basename="admin-log")
router.register("features", v.FeatureAdminViewSet, basename="admin-feature")
urlpatterns = [path("stats/", v.StatsView.as_view()), path("broadcast/", v.BroadcastView.as_view()),
               path("storage/", v.StorageAdminView.as_view())] + router.urls
