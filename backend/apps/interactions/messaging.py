"""
Personal messaging between two members.

Who may write to whom (checked on every message, on the server):
- the sender's own profile is approved (active);
- the other member's profile is discoverable (approved, visible to members,
  active account), not the sender's own, and of the opposite gender;
- an interest between them was accepted, in either direction. Messaging is a
  step after mutual consent, so nobody receives messages they didn't agree to;
- starting a conversation needs Feature.MESSAGING (Silver, Gold, Diamond). The
  member who was written to may always reply, whatever their package, and the
  member who started it keeps writing only while they still have the benefit.

Reading: a member only ever sees conversations they are part of. Every lookup
is by (the signed-in member, the other member's Matrimony ID), so there's no
conversation id to guess. Opening a conversation marks the other member's
messages as read. Messages carry only their text and time: no phone number,
email or other private detail is added to any messaging response.

The project has no block or report feature yet; when one is added, it must be
checked in `messaging_access` too.
"""
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.memberships.entitlements import UPGRADE_MESSAGES, Feature, entitlements_for
from apps.notifications.models import NotificationKind
from apps.notifications.services import notify
from apps.profiles.choices import ProfileStatus
from apps.profiles.models import Profile
from apps.profiles.services import has_accepted_interest

from .models import Conversation, Message
from .services import InteractionError

MAX_LENGTH = 2000


class MessagingAccess:
    """Whether the member may write to the other member now. The values are API codes."""

    AVAILABLE = "available"
    PROFILE_NOT_ACTIVE = "profile_not_active"
    UNAVAILABLE = "unavailable"  # the other member's profile isn't visible any more
    INTEREST_REQUIRED = "interest_required"
    UPGRADE_REQUIRED = "upgrade_required"


MESSAGES = {
    MessagingAccess.PROFILE_NOT_ACTIVE: "Your profile must be approved before you can send messages.",
    MessagingAccess.UNAVAILABLE: "This member's profile isn't available, so you can't send them messages.",
    MessagingAccess.INTEREST_REQUIRED: "You can message a member once one of you has accepted the other's interest.",
    MessagingAccess.UPGRADE_REQUIRED: UPGRADE_MESSAGES[Feature.MESSAGING],
}


def _pair(a: Profile, b: Profile) -> tuple[Profile, Profile]:
    return (a, b) if a.pk < b.pk else (b, a)


def conversation_between(a: Profile, b: Profile) -> Conversation | None:
    first, second = _pair(a, b)
    return Conversation.objects.filter(member_a=first, member_b=second).first()


def messaging_access(me: Profile, other: Profile, conversation: Conversation | None = None) -> str:
    if me.status != ProfileStatus.ACTIVE:
        return MessagingAccess.PROFILE_NOT_ACTIVE
    if (
        other.pk == me.pk
        or other.gender == me.gender
        or not Profile.objects.discoverable().filter(pk=other.pk).exists()
    ):
        return MessagingAccess.UNAVAILABLE
    if not has_accepted_interest(me, other):
        return MessagingAccess.INTEREST_REQUIRED
    replying = conversation is not None and conversation.started_by_id != me.pk
    if not replying and not entitlements_for(me.user).has(Feature.MESSAGING):
        return MessagingAccess.UPGRADE_REQUIRED
    return MessagingAccess.AVAILABLE


def access_data(access: str) -> dict:
    return {"can_send": access == MessagingAccess.AVAILABLE, "code": access, "message": MESSAGES.get(access, "")}


def clean_body(body) -> str:
    text = body.strip() if isinstance(body, str) else ""
    if not text:
        raise InteractionError("Write a message first.", code="empty", status=400)
    if len(text) > MAX_LENGTH:
        raise InteractionError(f"Keep messages under {MAX_LENGTH} characters.", code="too_long", status=400)
    return text


def send_message(me: Profile, other: Profile, body) -> Message:
    text = clean_body(body)
    with transaction.atomic():
        conversation = conversation_between(me, other)
        if conversation is not None:
            conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
        access = messaging_access(me, other, conversation)
        if access != MessagingAccess.AVAILABLE:
            raise InteractionError(MESSAGES[access], code=access, status=403)
        now = timezone.now()
        if conversation is None:
            first, second = _pair(me, other)
            try:
                with transaction.atomic():
                    conversation = Conversation.objects.create(
                        member_a=first, member_b=second, started_by=me, last_message_at=now
                    )
            except IntegrityError:
                # The other member started it at the same moment: this message is a reply.
                conversation = Conversation.objects.select_for_update().get(member_a=first, member_b=second)
        # Notify once per batch of unread messages, not for every message.
        other_had_unread = conversation.messages.filter(sender=me, read_at=None).exists()
        message = Message.objects.create(conversation=conversation, sender=me, body=text)
        conversation.last_message_at = now
        conversation.save(update_fields=["last_message_at", "updated_at"])
        if not other_had_unread:
            notify(
                other.user,
                NotificationKind.MESSAGE_RECEIVED,
                "You have a new message",
                f"{me.display_name} ({me.profile_code}) sent you a message.",
                f"/dashboard/messages/{me.profile_code}",
            )
    return message


def mark_read(conversation: Conversation, me: Profile) -> int:
    return conversation.messages.filter(read_at=None).exclude(sender=me).update(read_at=timezone.now())


def conversations_for(me: Profile) -> QuerySet:
    """The member's conversations, latest first, each with `unread` (messages to `me` not yet read)."""
    return (
        Conversation.objects.filter(Q(member_a=me) | Q(member_b=me))
        .select_related("member_a__user", "member_b__user")
        .annotate(unread=Count("messages", filter=Q(messages__read_at=None) & ~Q(messages__sender=me)))
        .order_by("-last_message_at", "-pk")
    )


def unread_count(me: Profile) -> int:
    return (
        Message.objects.filter(Q(conversation__member_a=me) | Q(conversation__member_b=me), read_at=None)
        .exclude(sender=me)
        .count()
    )
