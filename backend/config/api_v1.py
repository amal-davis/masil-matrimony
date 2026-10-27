"""Routes for version 1 of the API, mounted at /api/v1/."""
from django.conf import settings
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.memberships.views import (
    ContactExchangeDecisionView,
    ContactExchangeListView,
    MyAssistanceDetailView,
    MyAssistanceView,
    MyCaseRequirementsView,
    MyConsultationsView,
    MyConsultationView,
    MyFamilyContactView,
    MyFamilyView,
    MyMembershipView,
    PackageListView,
    SuggestionResponseView,
)
from apps.profiles.dashboard import DashboardSummaryView

urlpatterns = [
    path("", include("apps.core.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("enquiries/", include("apps.enquiries.urls")),
    path("profiles/", include("apps.profiles.urls")),
    path("", include("apps.interactions.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("payments/", include("apps.payments.urls")),
    path("success-stories/", include("apps.website_content.urls")),
    path("memberships/packages/", PackageListView.as_view(), name="membership-packages"),
    path("memberships/me/", MyMembershipView.as_view(), name="membership-me"),
    path("memberships/me/assistance/", MyAssistanceView.as_view(), name="membership-assistance"),
    path("memberships/me/assistance/<uuid:case_id>/", MyAssistanceDetailView.as_view(), name="membership-assistance-case"),
    path(
        "memberships/me/assistance/<uuid:case_id>/requirements/",
        MyCaseRequirementsView.as_view(),
        name="membership-assistance-requirements",
    ),
    path(
        "memberships/me/assistance/<uuid:case_id>/consultations/",
        MyConsultationsView.as_view(),
        name="membership-assistance-consultations",
    ),
    path(
        "memberships/me/assistance/<uuid:case_id>/consultations/<uuid:consultation_id>/",
        MyConsultationView.as_view(),
        name="membership-assistance-consultation",
    ),
    path("memberships/me/assistance/<uuid:case_id>/family/", MyFamilyView.as_view(), name="membership-assistance-family"),
    path(
        "memberships/me/assistance/<uuid:case_id>/family/<uuid:contact_id>/",
        MyFamilyContactView.as_view(),
        name="membership-assistance-family-contact",
    ),
    path(
        "memberships/me/assistance/<uuid:case_id>/suggestions/<str:profile_code>/",
        SuggestionResponseView.as_view(),
        name="membership-assistance-suggestion",
    ),
    path("memberships/contact-exchanges/", ContactExchangeListView.as_view(), name="contact-exchanges"),
    path(
        "memberships/contact-exchanges/<uuid:exchange_id>/",
        ContactExchangeDecisionView.as_view(),
        name="contact-exchange-decision",
    ),
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
]

if settings.API_DOCS_ENABLED:
    urlpatterns += [
        path("schema/", SpectacularAPIView.as_view(), name="api-schema"),
        path("docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    ]
