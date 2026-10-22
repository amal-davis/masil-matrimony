from django.urls import path

from .views import (
    InterestActionView,
    ReceivedInterestsView,
    SendInterestView,
    SentInterestsView,
    ShortlistEntryView,
    ShortlistView,
)

app_name = "interactions"

urlpatterns = [
    path("interests/", SendInterestView.as_view(), name="interest-send"),
    path("interests/received/", ReceivedInterestsView.as_view(), name="interests-received"),
    path("interests/sent/", SentInterestsView.as_view(), name="interests-sent"),
    path("interests/<uuid:interest_id>/accept/", InterestActionView.as_view(action="accept"), name="interest-accept"),
    path("interests/<uuid:interest_id>/decline/", InterestActionView.as_view(action="decline"), name="interest-decline"),
    path(
        "interests/<uuid:interest_id>/withdraw/", InterestActionView.as_view(action="withdraw"), name="interest-withdraw"
    ),
    path("shortlist/", ShortlistView.as_view(), name="shortlist"),
    path("shortlist/<str:profile_code>/", ShortlistEntryView.as_view(), name="shortlist-entry"),
]
