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
from apps.memberships.entitlements import Feature, entitlements_for, upgrade_required

from . import access, highlights, matching, search, services, verification
from .models import Profile, ProfilePhoto
from .photos import PhotoRejected, photo_id_from_token
from .serializers import (
    CreateProfileSerializer,
    OwnPhotoSerializer,
    OwnProfileSerializer,
    PartnerPreferenceSerializer,
    card_data,
    detail_data,
    public_detail_data,
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


class VerificationRequestView(MemberAPIView):
    """POST: ask staff to verify the member's identity for the Verified badge (apps.profiles.verification)."""

    @extend_schema(request=None, responses=OwnProfileSerializer, tags=["profiles"])
    def post(self, request):
        profile = own_profile(request)
        try:
            verification.request_verification(profile)
        except verification.VerificationError as error:
            body = {"detail": error.message, "code": error.code}
            if error.feature:
                body = upgrade_required(error.feature)
            return Response(body, status=error.status)
        return Response(OwnProfileSerializer(profile).data)


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


class MemberOrVisitor(IsMember):
    """Visitors who aren't signed in, and members (who must pass IsMember as everywhere else)."""

    def has_permission(self, request, view):
        return not request.user.is_authenticated or super().has_permission(request, view)


def private_response(data, status_code=status.HTTP_200_OK) -> Response:
    """Differs per viewer, so no shared cache (browser, proxy or CDN) may store or reuse it."""
    response = Response(data, status=status_code)
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Authorization, Cookie"
    return response


class ProfileDetailView(MemberAPIView):
    """
    Another member's profile (or your own), cut to the requester's access level
    (apps.profiles.access): a visitor's public view, a member's basic view, or the
    full view with an eligible membership. Unknown or hidden profiles are 404 to
    members; visitors get 401 for any profile they may not see, so a profile's
    existence isn't revealed.
    """

    permission_classes = [MemberOrVisitor]

    @extend_schema(tags=["profiles"])
    def get(self, request, profile_code):
        profile = (
            Profile.objects.select_related("user", "partner_preference")
            .prefetch_related(services.approved_photos_prefetch())
            .filter(profile_code=profile_code.upper())
            .first()
        )
        if not request.user.is_authenticated:
            level = access.public_access(profile) if profile is not None else None
            if level is None:
                return private_response(
                    {"detail": "Sign in to view this profile.", "code": "sign_in_required"},
                    status.HTTP_401_UNAUTHORIZED,
                )
            return private_response(public_detail_data(profile, request, level))

        viewer = services.viewer_profile(request.user)
        if viewer is None:
            raise PermissionDenied(
                {"detail": "Create your profile to view other members' profiles.", "code": "no_profile"}
            )
        if profile is None or not services.can_view_profile(viewer, profile):
            raise NotFound("Profile not found.")
        from apps.interactions.profile_views import record_view

        record_view(viewer, profile)
        return private_response(detail_data(viewer, profile, request, access.member_access(viewer, profile)))


class HighlightedProfilesView(APIView):
    """
    The homepage's Highlighted Profiles: public, read-only, at most 12
    (apps.profiles.highlights). `?limit=` asks for fewer.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["profiles"])
    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", highlights.MAX_HIGHLIGHTED))
        except ValueError:
            limit = highlights.MAX_HIGHLIGHTED
        return Response([highlights.public_card(item, request) for item in highlights.highlighted_profiles(limit)])


class ProfileSearchView(MemberAPIView):
    """
    Search approved profiles by the filters the member chose (apps.profiles.search
    documents the filters and who can be found). Members only, like profile pages:
    the searcher is always the signed-in member, never chosen by the request.
    """

    @extend_schema(tags=["profiles"])
    def get(self, request):
        from apps.interactions.models import Shortlist

        viewer = services.viewer_profile(request.user)
        if viewer is None:
            raise PermissionDenied({"detail": "Create your profile to search other members' profiles.", "code": "no_profile"})
        filters = search.SearchFilters.from_query(request.query_params, context={"viewer": viewer})
        filters.is_valid(raise_exception=True)
        advanced = entitlements_for(request.user).has(Feature.ADVANCED_SEARCH)
        used = [name for name in search.ADVANCED_FILTERS if filters.validated_data.get(name)]
        if used and not advanced:
            return private_response(
                {**upgrade_required(Feature.ADVANCED_SEARCH), "filters": used}, status.HTTP_403_FORBIDDEN
            )
        results = (
            search.search_profiles(viewer, filters.validated_data)
            .select_related("user")
            .prefetch_related(services.approved_photos_prefetch())
        )
        shortlisted = set(Shortlist.objects.filter(owner=viewer).values_list("profile_id", flat=True))
        accepted = services.accepted_partner_ids(viewer)
        response = paginated(
            self,
            results,
            lambda profile: {
                **card_data(viewer, profile, request, accepted_ids=accepted),
                "shortlisted": profile.pk in shortlisted,
            },
        )
        response.data["searching_for"] = search.searchable_gender(viewer)
        response.data["advanced_search"] = advanced
        return response


class MatchesView(MemberAPIView):
    """
    The member's matches from their saved partner preferences (apps.profiles.matching),
    best first, with a 0-100 score and the reasons. `?mutual=1` keeps only mutual
    matches. The member is always the signed-in user: nothing in the request
    selects whose matches these are.
    """

    @extend_schema(tags=["profiles"])
    def get(self, request):
        from apps.interactions.models import Shortlist

        from apps.matchmaking.engine import gate_for_member

        profile = own_profile(request)
        mutual_only = request.query_params.get("mutual") in ("1", "true")
        # Live results from the engine, minus suggestions the member hid or staff dismissed
        # (and, when staff review is required, only approved ones: apps.matchmaking.engine).
        candidates = (
            gate_for_member(profile, matching.ranked_candidates(profile, mutual_only=mutual_only))
            .select_related("user", "partner_preference")
            .prefetch_related(services.approved_photos_prefetch())
        )
        shortlisted = set(Shortlist.objects.filter(owner=profile).values_list("profile_id", flat=True))
        accepted = services.accepted_partner_ids(profile)
        response = paginated(
            self,
            candidates,
            lambda match: {
                **card_data(profile, match, request, accepted_ids=accepted),
                "shortlisted": match.pk in shortlisted,
                "match": matching.explain(profile, match).as_dict(),
            },
        )
        response.data["preferences_set"] = matching.has_preferences(matching.preference_of(profile))
        response.data["mutual_only"] = mutual_only
        return response


class HideMatchView(MemberAPIView):
    """
    POST: hide a suggested profile from the signed-in member's matches. Only ever
    the member's own list; it tells the other member nothing.
    """

    @extend_schema(request=None, tags=["profiles"])
    def post(self, request, profile_code):
        from apps.matchmaking.engine import hide_for_member

        profile = own_profile(request)
        candidate = Profile.objects.discoverable().exclude(pk=profile.pk).filter(profile_code=profile_code.upper()).first()
        if candidate is None:
            return Response({"detail": "Profile not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        hide_for_member(profile, candidate)
        return Response(status=status.HTTP_204_NO_CONTENT)
