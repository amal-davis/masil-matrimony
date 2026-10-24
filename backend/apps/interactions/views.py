from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response

from apps.profiles.models import Profile
from apps.profiles.serializers import card_data
from apps.profiles.views import MemberAPIView, own_profile, paginated

from . import services
from .models import Interest, InterestStatus, Shortlist


def other_member(viewer: Profile, other: Profile, request) -> dict:
    """The other member in an interest or shortlist entry, or a minimal stub if they're no longer visible."""
    if Profile.objects.discoverable().filter(pk=other.pk).exists():
        return {**card_data(viewer, other, request), "available": True}
    return {"profile_code": other.profile_code, "display_name": other.display_name, "available": False}


def interest_data(viewer: Profile, interest: Interest, other: Profile, request) -> dict:
    return {
        "id": str(interest.public_id),
        "status": interest.status,
        "created_at": interest.created_at,
        "responded_at": interest.responded_at,
        "profile": other_member(viewer, other, request),
    }


def error_response(error: services.InteractionError) -> Response:
    return Response({"detail": error.message, "code": error.code}, status=error.status)


def status_filter(request):
    value = request.query_params.get("status", "")
    if value and value not in InterestStatus.values:
        raise serializers.ValidationError({"status": f"Use one of: {', '.join(InterestStatus.values)}."})
    return value


class ProfileCodeSerializer(serializers.Serializer):
    profile_code = serializers.RegexField(r"^[A-Za-z0-9]{4,12}$")


class SendInterestView(MemberAPIView):
    throttle_scope = "interest_send"

    @extend_schema(request=ProfileCodeSerializer, tags=["interests"])
    def post(self, request):
        sender = own_profile(request)
        payload = ProfileCodeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            interest = services.send_interest(sender, payload.validated_data["profile_code"])
        except services.InteractionError as error:
            return error_response(error)
        return Response(interest_data(sender, interest, interest.receiver, request), status=status.HTTP_201_CREATED)


class ReceivedInterestsView(MemberAPIView):
    @extend_schema(tags=["interests"])
    def get(self, request):
        profile = own_profile(request)
        queryset = Interest.objects.filter(receiver=profile).exclude(status=InterestStatus.WITHDRAWN)
        if wanted := status_filter(request):
            queryset = queryset.filter(status=wanted)
        queryset = queryset.select_related("sender__user").order_by("-created_at")
        return paginated(self, queryset, lambda item: interest_data(profile, item, item.sender, request))


class SentInterestsView(MemberAPIView):
    @extend_schema(tags=["interests"])
    def get(self, request):
        profile = own_profile(request)
        queryset = Interest.objects.filter(sender=profile)
        if wanted := status_filter(request):
            queryset = queryset.filter(status=wanted)
        queryset = queryset.select_related("receiver__user").order_by("-created_at")
        return paginated(self, queryset, lambda item: interest_data(profile, item, item.receiver, request))


class InterestActionView(MemberAPIView):
    """POST /interests/<id>/accept|decline (receiver only) or /withdraw (sender only)."""

    action = ""

    @extend_schema(request=None, tags=["interests"])
    def post(self, request, interest_id):
        profile = own_profile(request)
        try:
            if self.action == "withdraw":
                interest = services.withdraw_interest(profile, interest_id)
                other = interest.receiver
            else:
                interest = services.respond_to_interest(profile, interest_id, accept=self.action == "accept")
                other = interest.sender
        except services.InteractionError as error:
            return error_response(error)
        return Response(interest_data(profile, interest, other, request))


class ShortlistView(MemberAPIView):
    @extend_schema(tags=["shortlist"])
    def get(self, request):
        profile = own_profile(request)
        queryset = Shortlist.objects.filter(owner=profile).select_related("profile__user")
        return paginated(
            self,
            queryset,
            lambda entry: {"created_at": entry.created_at, "profile": other_member(profile, entry.profile, request)},
        )

    @extend_schema(request=ProfileCodeSerializer, tags=["shortlist"])
    def post(self, request):
        profile = own_profile(request)
        payload = ProfileCodeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            entry = services.add_to_shortlist(profile, payload.validated_data["profile_code"])
        except services.InteractionError as error:
            return error_response(error)
        return Response(
            {"created_at": entry.created_at, "profile": other_member(profile, entry.profile, request)},
            status=status.HTTP_201_CREATED,
        )


class ShortlistEntryView(MemberAPIView):
    @extend_schema(responses={204: None}, tags=["shortlist"])
    def delete(self, request, profile_code):
        services.remove_from_shortlist(own_profile(request), profile_code)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContactNumberView(MemberAPIView):
    """
    GET: whether the member may view this profile's mobile number (never the number).
    POST: view it, using one of the subscription's contact views unless it was
    already viewed during the subscription.
    """

    throttle_scope = "contact_view"

    def get_throttles(self):
        # Only viewing is throttled; checking the status is part of loading a profile.
        return super().get_throttles() if self.request.method == "POST" else []

    @extend_schema(tags=["contact"])
    def get(self, request, profile_code):
        viewer = own_profile(request)
        try:
            profile = services.discoverable_profile(profile_code)
        except services.InteractionError as error:
            return error_response(error)
        return Response(services.contact_status(viewer, profile))

    @extend_schema(request=None, tags=["contact"])
    def post(self, request, profile_code):
        viewer = own_profile(request)
        try:
            summary, phone_number = services.view_contact(viewer, profile_code)
        except services.InteractionError as error:
            return error_response(error)
        return Response({**summary, "phone_number": phone_number})
