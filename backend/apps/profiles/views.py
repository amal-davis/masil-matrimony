import logging

from django.http import FileResponse, Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsMember

from . import services
from .models import Profile, ProfilePhoto
from .photos import PhotoRejected, photo_id_from_token
from .serializers import (
    CreateProfileSerializer,
    OwnPhotoSerializer,
    OwnProfileSerializer,
    PartnerPreferenceSerializer,
    card_data,
    detail_data,
)

logger = logging.getLogger(__name__)


def own_profile(request) -> Profile:
    """The signed-in member's profile. Always derived from the request, never from client input."""
    profile = Profile.objects.select_related("partner_preference").filter(user=request.user).first()
    if profile is None:
        raise NotFound({"detail": "You haven't created your profile yet.", "code": "no_profile"})
    return profile


def rule_error(error: services.ProfileRuleError) -> Response:
    return Response({"detail": error.message, "code": error.code}, status=status.HTTP_409_CONFLICT)


def paginated(view, queryset, to_data):
    paginator = view.paginator
    page = paginator.paginate_queryset(queryset, view.request, view=view)
    return paginator.get_paginated_response([to_data(item) for item in page])


class MemberAPIView(APIView):
    permission_classes = [IsMember]

    @property
    def paginator(self):
        if not hasattr(self, "_paginator"):
            from rest_framework.settings import api_settings

            self._paginator = api_settings.DEFAULT_PAGINATION_CLASS()
        return self._paginator


class OwnProfileView(MemberAPIView):
    """GET / POST (create) / PATCH (update any subset of fields) the member's own profile."""

    @extend_schema(responses=OwnProfileSerializer, tags=["profiles"])
    def get(self, request):
        return Response(OwnProfileSerializer(own_profile(request)).data)

    @extend_schema(request=CreateProfileSerializer, responses={201: OwnProfileSerializer}, tags=["profiles"])
    def post(self, request):
        if Profile.objects.filter(user=request.user).exists():
            return Response(
                {"detail": "You already have a profile.", "code": "profile_exists"}, status=status.HTTP_409_CONFLICT
            )
        serializer = CreateProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = services.create_profile(request.user, **serializer.validated_data)
        except services.ProfileRuleError as error:
            return rule_error(error)
        logger.info("Profile %s created", profile.profile_code)
        return Response(OwnProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=OwnProfileSerializer, responses=OwnProfileSerializer, tags=["profiles"])
    def patch(self, request):
        profile = own_profile(request)
        serializer = OwnProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OwnProfileSerializer(profile).data)


class OwnPartnerPreferenceView(MemberAPIView):
    @extend_schema(request=PartnerPreferenceSerializer, responses=PartnerPreferenceSerializer, tags=["profiles"])
    def patch(self, request):
        profile = own_profile(request)
        serializer = PartnerPreferenceSerializer(profile.partner_preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class SubmitProfileView(MemberAPIView):
    """Send a complete draft (or a profile returned for changes) to staff for review."""

    @extend_schema(request=None, responses=OwnProfileSerializer, tags=["profiles"])
    def post(self, request):
        profile = own_profile(request)
        try:
            services.submit_for_review(profile)
        except services.ProfileRuleError as error:
            return rule_error(error)
        return Response(OwnProfileSerializer(profile).data)


class OwnPhotosView(MemberAPIView):
    """List the member's photos (with review status) or upload a new one (multipart field `photo`)."""

    parser_classes = [MultiPartParser]
    throttle_scope = "photo_upload"

    def get_throttles(self):
        # Only uploads are rate limited; listing is ordinary traffic.
        return super().get_throttles() if self.request.method == "POST" else []

    @extend_schema(responses=OwnPhotoSerializer(many=True), tags=["profiles"])
    def get(self, request):
        photos = own_profile(request).photos.all()
        return Response(OwnPhotoSerializer(photos, many=True, context={"request": request}).data)

    @extend_schema(request={"multipart/form-data": {"type": "object", "properties": {"photo": {"type": "string", "format": "binary"}}}},
                   responses={201: OwnPhotoSerializer}, tags=["profiles"])
    def post(self, request):
        profile = own_profile(request)
        upload = request.FILES.get("photo")
        if upload is None:
            raise ValidationError({"photo": "Choose a photo to upload."})
        try:
            photo = services.add_photo(profile, upload)
        except PhotoRejected as error:
            raise ValidationError({"photo": str(error)}) from error
        except services.ProfileRuleError as error:
            return rule_error(error)
        logger.info("Photo %s uploaded for profile %s", photo.public_id, profile.profile_code)
        return Response(OwnPhotoSerializer(photo, context={"request": request}).data, status=status.HTTP_201_CREATED)


def own_photo(request, photo_id) -> tuple[Profile, ProfilePhoto]:
    profile = own_profile(request)
    # Scoped to the member's own profile: another member's photo id is simply "not found".
    photo = profile.photos.filter(public_id=photo_id).first()
    if photo is None:
        raise NotFound("Photo not found.")
    return profile, photo


class OwnPhotoView(MemberAPIView):
    @extend_schema(responses={204: None}, tags=["profiles"])
    def delete(self, request, photo_id):
        profile, photo = own_photo(request, photo_id)
        services.delete_photo(profile, photo)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OwnPrimaryPhotoView(MemberAPIView):
    @extend_schema(request=None, responses=OwnPhotoSerializer(many=True), tags=["profiles"])
    def post(self, request, photo_id):
        profile, photo = own_photo(request, photo_id)
        try:
            services.set_primary_photo(profile, photo)
        except services.ProfileRuleError as error:
            return rule_error(error)
        return Response(OwnPhotoSerializer(profile.photos.all(), many=True, context={"request": request}).data)


class PhotoFileView(APIView):
    """
    Serves a photo file for a signed, expiring URL minted by the API for someone
    allowed to see it. No session or token is needed, so <img> tags work, but the
    URL can't be guessed and stops working after PHOTO_URL_TTL_SECONDS.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(exclude=True)
    def get(self, request, token):
        photo_hex = photo_id_from_token(token)
        photo = ProfilePhoto.objects.filter(public_id=photo_hex).first() if photo_hex else None
        if photo is None:
            raise Http404
        try:
            file = photo.image.open("rb")
        except FileNotFoundError:
            logger.error("Photo file missing for %s", photo.public_id)
            raise Http404 from None
        response = FileResponse(file, content_type="image/jpeg")
        response["Cache-Control"] = "private, max-age=3600"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'"
        return response


class ProfileDetailView(MemberAPIView):
    """Another member's profile (or your own), privacy-filtered. Unknown or hidden profiles are 404."""

    @extend_schema(tags=["profiles"])
    def get(self, request, profile_code):
        viewer = services.viewer_profile(request.user)
        if viewer is None:
            raise PermissionDenied(
                {"detail": "Create your profile to view other members' profiles.", "code": "no_profile"}
            )
        profile = (
            Profile.objects.select_related("user", "partner_preference")
            .filter(profile_code=profile_code.upper())
            .first()
        )
        if profile is None or not services.can_view_profile(viewer, profile):
            raise NotFound("Profile not found.")
        return Response(detail_data(viewer, profile, request))


class MatchesView(MemberAPIView):
    @extend_schema(tags=["profiles"])
    def get(self, request):
        from apps.interactions.models import Shortlist

        profile = own_profile(request)
        shortlisted = set(Shortlist.objects.filter(owner=profile).values_list("profile_id", flat=True))
        return paginated(
            self,
            services.matches_for(profile),
            lambda match: {**card_data(profile, match, request), "shortlisted": match.pk in shortlisted},
        )
