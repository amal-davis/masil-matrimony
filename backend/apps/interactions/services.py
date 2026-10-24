"""
Interest, shortlist and contact-access rules. Every change runs in a
transaction with the relevant rows locked, so two clicks (or two devices) can't
produce contradictory results or get past a package limit, and notifications
are written in the same transaction.
"""
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.memberships.entitlements import entitlements_for
from apps.notifications.models import NotificationKind
from apps.notifications.services import notify
from apps.profiles.choices import ContactSharing, ProfileStatus
from apps.profiles.models import Profile

from .models import ContactView, Interest, InterestStatus, Shortlist


class InteractionError(Exception):
    """A request that breaks an interest/shortlist rule; the message is safe to show."""

    def __init__(self, message, code, status=409):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def discoverable_profile(code: str) -> Profile:
    profile = Profile.objects.discoverable().filter(profile_code=code.upper()).first()
    if profile is None:
        raise InteractionError("Profile not found.", code="not_found", status=404)
    return profile


def send_interest(sender: Profile, receiver_code: str) -> Interest:
    if sender.status != ProfileStatus.ACTIVE:
        raise InteractionError(
            "Your profile must be approved before you can send interests.", code="profile_not_active", status=403
        )
    receiver = discoverable_profile(receiver_code)
    if receiver.pk == sender.pk:
        raise InteractionError("You can't send an interest to yourself.", code="self")
    if receiver.gender == sender.gender:
        raise InteractionError("Interests can only be sent to brides or grooms.", code="same_gender")

    with transaction.atomic():
        # Lock the sender first so simultaneous sends can't both pass the Free limit check.
        Profile.objects.select_for_update().filter(pk=sender.pk).first()
        entitlements = entitlements_for(sender.user)
        reverse = Interest.objects.select_for_update().filter(sender=receiver, receiver=sender).first()
        if reverse and reverse.status in (InterestStatus.PENDING, InterestStatus.ACCEPTED):
            raise InteractionError(
                "This member has already sent you an interest. You can respond to it instead.",
                code="reverse_exists",
            )
        existing = Interest.objects.select_for_update().filter(sender=sender, receiver=receiver).first()
        if existing:
            if existing.status != InterestStatus.WITHDRAWN:
                raise InteractionError("You've already sent an interest to this member.", code="duplicate")
            # A withdrawn interest may be sent again: it becomes a fresh pending interest. It
            # counts toward the Free limit only if it didn't already.
            if entitlements.is_free and not existing.counts_toward_free_limit:
                _check_free_interest_limit(sender, entitlements)
                existing.counts_toward_free_limit = True
            existing.status = InterestStatus.PENDING
            existing.responded_at = None
            existing.created_at = timezone.now()
            existing.save(
                update_fields=["status", "responded_at", "created_at", "counts_toward_free_limit", "updated_at"]
            )
            interest = existing
        else:
            if entitlements.is_free:
                _check_free_interest_limit(sender, entitlements)
            try:
                with transaction.atomic():
                    interest = Interest.objects.create(
                        sender=sender, receiver=receiver, counts_toward_free_limit=entitlements.is_free
                    )
            except IntegrityError:
                # A simultaneous request created it first.
                raise InteractionError("You've already sent an interest to this member.", code="duplicate") from None
        notify(
            receiver.user,
            NotificationKind.INTEREST_RECEIVED,
            "You've received a new interest",
            f"{sender.display_name} ({sender.profile_code}) is interested in your profile.",
            "/dashboard/interests/received",
        )
    return interest


def free_interests_used(profile: Profile | None) -> int:
    """Interests that count toward the Free package's limit (one per member, ever; no reset)."""
    if profile is None:
        return 0
    return Interest.objects.filter(sender=profile, counts_toward_free_limit=True).count()


def _check_free_interest_limit(sender: Profile, entitlements) -> None:
    limit = entitlements.outgoing_interest_limit
    if limit is not None and free_interests_used(sender) >= limit:
        raise InteractionError(
            f"You've sent all {limit} interests included with {entitlements.package.name}. "
            "Upgrade to a paid membership to send more.",
            code="interest_limit_reached",
            status=403,
        )


def _locked_interest(interest_id, **ownership) -> Interest:
    interest = (
        Interest.objects.select_for_update()
        .select_related("sender__user", "receiver__user")
        .filter(public_id=interest_id, **ownership)
        .first()
    )
    if interest is None:
        # Also the answer for someone else's interest: don't reveal it exists.
        raise InteractionError("Interest not found.", code="not_found", status=404)
    return interest


def respond_to_interest(receiver: Profile, interest_id, accept: bool) -> Interest:
    with transaction.atomic():
        interest = _locked_interest(interest_id, receiver=receiver)
        if interest.status != InterestStatus.PENDING:
            raise InteractionError(
                f"This interest has already been {interest.get_status_display().lower()}.", code="not_pending"
            )
        interest.status = InterestStatus.ACCEPTED if accept else InterestStatus.DECLINED
        interest.responded_at = timezone.now()
        interest.save(update_fields=["status", "responded_at", "updated_at"])
        notify(
            interest.sender.user,
            NotificationKind.INTEREST_ACCEPTED if accept else NotificationKind.INTEREST_DECLINED,
            "Your interest was accepted" if accept else "Your interest was declined",
            f"{receiver.display_name} ({receiver.profile_code}) "
            f"{'accepted' if accept else 'declined'} your interest.",
            "/dashboard/interests/sent",
        )
    return interest


def withdraw_interest(sender: Profile, interest_id) -> Interest:
    with transaction.atomic():
        interest = _locked_interest(interest_id, sender=sender)
        if interest.status != InterestStatus.PENDING:
            raise InteractionError("Only interests awaiting a response can be withdrawn.", code="not_pending")
        interest.status = InterestStatus.WITHDRAWN
        interest.responded_at = timezone.now()
        interest.save(update_fields=["status", "responded_at", "updated_at"])
    return interest


def add_to_shortlist(owner: Profile, profile_code: str) -> Shortlist:
    profile = discoverable_profile(profile_code)
    if profile.pk == owner.pk:
        raise InteractionError("You can't shortlist your own profile.", code="self")
    try:
        with transaction.atomic():
            entry, _ = Shortlist.objects.get_or_create(owner=owner, profile=profile)
    except IntegrityError:
        # Created by a simultaneous request; adding twice is harmless.
        entry = Shortlist.objects.get(owner=owner, profile=profile)
    return entry


def remove_from_shortlist(owner: Profile, profile_code: str) -> None:
    Shortlist.objects.filter(owner=owner, profile__profile_code=profile_code.upper()).delete()


# --------------------------------------------------------------------------
# Contact numbers
# --------------------------------------------------------------------------


class ContactAccess:
    """Why a member can or can't see another member's number. The values are API codes."""

    AVAILABLE = "available"  # can view; uses one of the subscription's contact views
    VIEWED = "viewed"  # already viewed during this subscription; viewing again is free
    PROFILE_NOT_ACTIVE = "profile_not_active"  # the viewer's own profile isn't approved
    NOT_INCLUDED = "not_included"  # no current package with self-service contact access
    NOT_SHARED = "not_shared"  # the member hasn't agreed to share their number
    LIMIT_REACHED = "limit_reached"
    NO_NUMBER = "no_number"


CONTACT_MESSAGES = {
    ContactAccess.PROFILE_NOT_ACTIVE: "Your profile must be approved before you can view contact numbers.",
    ContactAccess.NOT_INCLUDED: (
        "Viewing contact numbers is included with the Silver, Gold and Diamond memberships. "
        "On assisted packages, your matchmaker coordinates contact."
    ),
    ContactAccess.NOT_SHARED: "This member hasn't chosen to share their mobile number.",
    ContactAccess.LIMIT_REACHED: "You've viewed all the contact numbers included with your membership.",
    ContactAccess.NO_NUMBER: "This member has no mobile number on file.",
}


def _contact_access(viewer: Profile, profile: Profile, subscription) -> str:
    if viewer.status != ProfileStatus.ACTIVE:
        return ContactAccess.PROFILE_NOT_ACTIVE
    if subscription is None or not subscription.contact_view_limit:
        return ContactAccess.NOT_INCLUDED
    # Checked before "viewed": a member who stops sharing is hidden from everyone at once.
    if profile.contact_sharing != ContactSharing.PAID_MEMBERS:
        return ContactAccess.NOT_SHARED
    if ContactView.objects.filter(subscription=subscription, profile=profile).exists():
        return ContactAccess.VIEWED
    if not profile.user.phone_number:
        return ContactAccess.NO_NUMBER
    if subscription.contact_views_used >= subscription.contact_view_limit:
        return ContactAccess.LIMIT_REACHED
    return ContactAccess.AVAILABLE


def _contact_summary(access: str, subscription) -> dict:
    has_limit = subscription is not None and bool(subscription.contact_view_limit)
    return {
        "access": access,
        "message": CONTACT_MESSAGES.get(access, ""),
        "limit": subscription.contact_view_limit if has_limit else None,
        "used": subscription.contact_views_used if has_limit else None,
    }


def contact_status(viewer: Profile, profile: Profile) -> dict:
    """Whether `viewer` may see `profile`'s number. Never includes the number."""
    subscription = entitlements_for(viewer.user).subscription
    return _contact_summary(_contact_access(viewer, profile, subscription), subscription)


def view_contact(viewer: Profile, profile_code: str) -> tuple[dict, str]:
    """
    Show `viewer` a member's mobile number, using one of their subscription's
    contact views unless they already viewed this member during it. Raises
    InteractionError when they may not.
    """
    profile = discoverable_profile(profile_code)
    if profile.pk == viewer.pk:
        raise InteractionError("This is your own profile.", code="self")
    with transaction.atomic():
        # Locking the subscription serialises a member's contact views, so the limit holds
        # under simultaneous requests.
        subscription = entitlements_for(viewer.user, lock=True).subscription
        access = _contact_access(viewer, profile, subscription)
        if access == ContactAccess.AVAILABLE:
            ContactView.objects.create(subscription=subscription, viewer=viewer, profile=profile)
            subscription.contact_views_used = F("contact_views_used") + 1
            subscription.save(update_fields=["contact_views_used", "updated_at"])
            subscription.refresh_from_db(fields=["contact_views_used"])
            access = ContactAccess.VIEWED
        elif access != ContactAccess.VIEWED:
            raise InteractionError(CONTACT_MESSAGES[access], code=access, status=403)
    return _contact_summary(access, subscription), profile.user.phone_number
