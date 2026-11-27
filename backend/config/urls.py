from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.meta import MetaView

api = [
    path("meta/", MetaView.as_view()),
    path("auth/", include("apps.accounts.urls")),
    path("users/", include("apps.users.urls")),
    path("", include("apps.workspaces.urls")),
    path("", include("apps.projects.urls")),
    path("", include("apps.materials.urls")),
    path("furniture/", include("apps.furniture.urls")),
    path("calculations/", include("apps.calculations.urls")),
    path("cutting-lists/", include("apps.cutting_lists.urls")),
    path("geometry/", include("apps.geometry.urls")),
    path("", include("apps.designs.urls")),
    path("", include("apps.conversations.urls")),
    path("", include("apps.galleries.urls")),
    path("", include("apps.files.urls")),
    path("", include("apps.workshops.urls")),
    path("", include("apps.rooms.urls")),
    path("subscriptions/", include("apps.subscriptions.urls")),
    path("", include("apps.notifications.urls")),
    path("analytics/", include("apps.analytics.urls")),
    path("admin-api/audit-logs/", include("apps.audit.urls")),
    path("marketplace/", include("apps.marketplace.urls")),
    path("ai/", include("apps.ai.urls")),
    path("app/", include("apps.releases.urls")),
    path("telegram/", include("apps.integrations.urls")),
    path("payments/", include("apps.finance.public_urls")),
    path("admin-api/finance/", include("apps.finance.urls")),
    path("admin-api/", include("apps.analytics.admin_urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/v1/", include(api)),
]
