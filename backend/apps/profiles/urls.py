from django.urls import path

from .views import (
    MatchesView,
    OwnPartnerPreferenceView,
    OwnPhotosView,
    OwnPhotoView,
    OwnPrimaryPhotoView,
    OwnProfileView,
    PhotoFileView,
    ProfileDetailView,
    SubmitProfileView,
)

app_name = "profiles"

urlpatterns = [
    path("me/", OwnProfileView.as_view(), name="me"),
    path("me/partner-preference/", OwnPartnerPreferenceView.as_view(), name="me-partner-preference"),
    path("me/submit/", SubmitProfileView.as_view(), name="me-submit"),
    path("me/photos/", OwnPhotosView.as_view(), name="me-photos"),
    path("me/photos/<uuid:photo_id>/", OwnPhotoView.as_view(), name="me-photo"),
    path("me/photos/<uuid:photo_id>/primary/", OwnPrimaryPhotoView.as_view(), name="me-photo-primary"),
    path("matches/", MatchesView.as_view(), name="matches"),
    path("photo-files/<str:token>/", PhotoFileView.as_view(), name="photo-file"),
    path("<str:profile_code>/", ProfileDetailView.as_view(), name="detail"),
]
