"""Routes for version 1 of the API, mounted at /api/v1/."""
from django.conf import settings
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.memberships.views import MyMembershipView, PackageListView
from apps.profiles.dashboard import DashboardSummaryView

urlpatterns = [
    path("", include("apps.core.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("enquiries/", include("apps.enquiries.urls")),
    path("profiles/", include("apps.profiles.urls")),
    path("", include("apps.interactions.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("memberships/packages/", PackageListView.as_view(), name="membership-packages"),
    path("memberships/me/", MyMembershipView.as_view(), name="membership-me"),
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
]

if settings.API_DOCS_ENABLED:
    urlpatterns += [
        path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
        path("docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    ]
