"""
Identity verification and the Verified Profile badge.

The badge means one thing: Massil staff checked the member's identity document
against their profile (name, date of birth, photo) and recorded the decision
in the admin. It is separate from profile review (every visible profile has
been reviewed) and from membership: paying never verifies anyone, and the badge
is never derived from a subscription.

1. A member whose package includes Feature.VERIFICATION (Silver, Gold, Diamond)
   asks for verification from their dashboard. Their profile must be approved
   and their mobile number verified. Asking again is refused while a request is
   waiting or once verified; after "not verified" they may ask again.
2. Verification staff contact the member, check the document offline, and use
   "Mark identity verified" or "Decline verification" in the admin. The admin
   records who decided and when (and logs it in the admin history); the member
   is notified. Documents are not uploaded to or stored by this system.
3. The badge ("verified": true) is shown on the profile wherever the member's
   card appears while the status is "verified". Staff can withdraw it with
   "Decline verification" (e.g. if a check is later found to be wrong).
"""
from django.db import transaction
from django.utils import timezone

from apps.memberships.entitlements import Feature, entitlements_for
from apps.notifications.models import NotificationKind
from apps.notifications.services import notify

from .choices import ProfileStatus, VerificationStatus
from .models import Profile


class VerificationError(Exception):
    def __init__(self, message, code, status=409, feature=None):
        super().__init__(message)
        self.message, self.code, self.status, self.feature = message, code, status, feature


def request_verification(profile: Profile) -> Profile:
    with transaction.atomic():
        locked = Profile.objects.select_for_update().select_related("user").get(pk=profile.pk)
        if not entitlements_for(locked.user).has(Feature.VERIFICATION):
            raise VerificationError("", code="upgrade_required", status=403, feature=Feature.VERIFICATION)
        if locked.status != ProfileStatus.ACTIVE:
            raise VerificationError(
                "Your profile must be approved before it can be verified.", code="profile_not_active", status=403
            )
        if locked.user.phone_verified_at is None:
            raise VerificationError("Verify your mobile number first.", code="phone_not_verified", status=403)
        if locked.verification_status == VerificationStatus.VERIFIED:
            raise VerificationError("Your profile is already verified.", code="already_verified")
        if locked.verification_status == VerificationStatus.REQUESTED:
            raise VerificationError("Your verification request is already with our team.", code="already_requested")
        locked.verification_status = VerificationStatus.REQUESTED
        locked.verification_requested_at = timezone.now()
        locked.verification_note = ""
        locked.save(update_fields=["verification_status", "verification_requested_at", "verification_note", "updated_at"])
    profile.refresh_from_db()
    return profile


def decide(profile: Profile, staff_user, verified: bool, note: str = "") -> bool:
    """Record a staff decision. Returns False (and changes nothing) when there is nothing to decide."""
    with transaction.atomic():
        locked = Profile.objects.select_for_update().select_related("user").get(pk=profile.pk)
        if verified:
            if locked.verification_status != VerificationStatus.REQUESTED or locked.status != ProfileStatus.ACTIVE:
                return False
            locked.verification_status = VerificationStatus.VERIFIED
            locked.verified_at = timezone.now()
            locked.verified_by = staff_user
            locked.verification_note = ""
            title, body = "Your profile is verified", "Members now see the Verified badge on your profile."
        else:
            if locked.verification_status not in (VerificationStatus.REQUESTED, VerificationStatus.VERIFIED):
                return False
            locked.verification_status = VerificationStatus.DECLINED
            locked.verified_at = None
            locked.verified_by = staff_user
            locked.verification_note = note[:255]
            title = "We couldn't verify your profile"
            body = note[:300] or "Please contact us for details. You can ask for verification again."
        locked.save(update_fields=["verification_status", "verified_at", "verified_by", "verification_note", "updated_at"])
        notify(locked.user, NotificationKind.VERIFICATION_DECIDED, title, body, "/dashboard/membership")
    return True
