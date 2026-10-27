from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response

from apps.memberships.entitlements import Feature, entitlements_for, upgrade_required
from apps.profiles.models import Profile
from apps.profiles.serializers import card_data
from apps.profiles.services import accepted_partner_ids
from apps.profiles.views import MemberAPIView, own_profile, paginated, private_response

from . import messaging, profile_views, services
from .models import Interest, InterestStatus, Message, Shortlist


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


def private_paginated(view, queryset, to_data) -> Response:
    """A page of per-member data that no shared cache may store."""
    response = paginated(view, queryset, to_data)
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Authorization, Cookie"
    return response


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
        return private_response(services.contact_status(viewer, profile))

    @extend_schema(request=None, tags=["contact"])
    def post(self, request, profile_code):
        viewer = own_profile(request)
        try:
            summary, phone_number = services.view_contact(viewer, profile_code)
        except services.InteractionError as error:
            return error_response(error)
        return private_response({**summary, "phone_number": phone_number})


# --------------------------------------------------------------------------
# Personal messages (apps.interactions.messaging)
# --------------------------------------------------------------------------


def message_data(message, me: Profile) -> dict:
    return {
        "id": str(message.public_id),
        "body": message.body,
        "sent_at": message.created_at,
        "mine": message.sender_id == me.pk,
        "read_at": message.read_at,
    }


def conversation_member(me: Profile, profile_code: str) -> Profile:
    """The other member of a conversation by Matrimony ID, if they're someone `me` could ever have written to."""
    other = (
        Profile.objects.select_related("user")
        .filter(profile_code=profile_code.upper())
        .exclude(pk=me.pk)
        .first()
    )
    if other is None or not (
        Profile.objects.discoverable().filter(pk=other.pk).exists() or messaging.conversation_between(me, other)
    ):
        raise services.InteractionError("Conversation not found.", code="not_found", status=404)
    return other


class MessageBodySerializer(serializers.Serializer):
    body = serializers.CharField(max_length=messaging.MAX_LENGTH, trim_whitespace=True)


class ConversationListView(MemberAPIView):
    """The member's conversations, latest first, with the other member and the last message."""

    @extend_schema(tags=["messages"])
    def get(self, request):
        me = own_profile(request)

        def item(conversation):
            last = conversation.messages.first()
            other = conversation.other(me)
            return {
                "profile": other_member(me, other, request),
                "last_message": message_data(last, me) if last else None,
                "unread": conversation.unread,
                "updated_at": conversation.last_message_at,
            }

        return private_paginated(self, messaging.conversations_for(me), item)


class ConversationView(MemberAPIView):
    """
    GET: the conversation with one member (newest messages first, paginated) and
    whether the member may write now; marks the other member's messages as read.
    POST {body}: send a message.
    """

    throttle_scope = "message_send"

    def get_throttles(self):
        return super().get_throttles() if self.request.method == "POST" else []

    @extend_schema(tags=["messages"])
    def get(self, request, profile_code):
        me = own_profile(request)
        try:
            other = conversation_member(me, profile_code)
        except services.InteractionError as error:
            return error_response(error)
        conversation = messaging.conversation_between(me, other)
        if conversation is not None and request.query_params.get("page", "1") == "1":
            messaging.mark_read(conversation, me)
        queryset = conversation.messages.all() if conversation else Message.objects.none()
        response = private_paginated(self, queryset, lambda message: message_data(message, me))
        response.data["profile"] = other_member(me, other, request)
        response.data["messaging"] = messaging.access_data(messaging.messaging_access(me, other, conversation))
        return response

    @extend_schema(request=MessageBodySerializer, tags=["messages"])
    def post(self, request, profile_code):
        me = own_profile(request)
        try:
            other = conversation_member(me, profile_code)
            message = messaging.send_message(me, other, request.data.get("body"))
        except services.InteractionError as error:
            return error_response(error)
        return private_response(message_data(message, me), status.HTTP_201_CREATED)


# --------------------------------------------------------------------------
# Who viewed my profile (apps.interactions.profile_views)
# --------------------------------------------------------------------------


class ProfileViewersView(MemberAPIView):
    """Members who viewed the signed-in member's profile, most recent first. Needs Feature.PROFILE_VIEWERS."""

    @extend_schema(tags=["profile views"])
    def get(self, request):
        me = own_profile(request)
        if not entitlements_for(request.user).has(Feature.PROFILE_VIEWERS):
            return private_response(
                {**upgrade_required(Feature.PROFILE_VIEWERS), "viewer_count": profile_views.viewer_count(me)},
                status.HTTP_403_FORBIDDEN,
            )
        accepted = accepted_partner_ids(me)
        return private_paginated(
            self,
            profile_views.viewers_of(me),
            lambda view: {
                "profile": {**card_data(me, view.viewer, request, accepted_ids=accepted), "available": True},
                "last_viewed_at": view.last_viewed_at,
                "visits": view.visits,
            },
        )
