"""
Interest and shortlist rules. Every change runs in a transaction with the
interest row locked, so two clicks (or two devices) can't produce contradictory
results, and notifications are written in the same transaction.
"""
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.notifications.models import NotificationKind
from apps.notifications.services import notify
from apps.profiles.choices import ProfileStatus
from apps.profiles.models import Profile

from .models import Interest, InterestStatus, Shortlist


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
            # A withdrawn interest may be sent again: it becomes a fresh pending interest.
            existing.status = InterestStatus.PENDING
            existing.responded_at = None
            existing.created_at = timezone.now()
            existing.save(update_fields=["status", "responded_at", "created_at", "updated_at"])
            interest = existing
        else:
            try:
                with transaction.atomic():
                    interest = Interest.objects.create(sender=sender, receiver=receiver)
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
