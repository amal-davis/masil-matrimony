"""
How much of another member's profile the requester may see. The one place
this is decided; GET /profiles/<code>/ (views.ProfileDetailView) uses it.

The requester is always the authenticated server-side user; nothing in the
request can claim a membership.

    PUBLIC   not signed in. Only for profiles featured on the homepage: the member
             agreed to be shown publicly if selected (Profile.homepage_consent) and
             staff selected them (Profile.is_highlighted). Only what that consent
             covers: given name, age, education, location and the main photo, if
             their photos are visible to all members. Any other profile (or an
             unknown code: no hint either way) asks the visitor to sign in.
    LIMITED  signed-in member without a membership that includes full profiles
             (Free; or a pending, cancelled or expired subscription): the basic
             section (the profile page's header) and at most one photo.
    FULL     a current subscription whose package includes full profiles
             (memberships.entitlements.FULL_PROFILE_PACKAGES), or the member's
             own profile: every section and every photo their privacy allows.

Every level also needs the profile to be discoverable (approved, visible to
members, active account; services.can_view_profile). Photo privacy
("accepted interests only") applies at every level. Contact numbers are never
part of a profile response: they need the separate contact flow
(apps.interactions.services.view_contact), with its own allowance.
The project has no blocking feature yet, so there's no block rule to apply.
"""
from dataclasses import dataclass

from apps.memberships.entitlements import Entitlements, entitlements_for

from .models import Profile


class AccessLevel:
    PUBLIC = "public"
    LIMITED = "limited"
    FULL = "full"


class Reason:
    """Why the level is what it is (API codes, for the page's prompt)."""

    SIGNED_OUT = "signed_out"
    NO_MEMBERSHIP = "no_membership"  # free member, or no current subscription
    PACKAGE_EXCLUDES = "package_excludes"  # current package without full profiles
    MEMBERSHIP = "membership"
    OWN_PROFILE = "own_profile"


@dataclass(frozen=True)
class ProfileAccess:
    level: str
    reason: str
    entitlements: Entitlements | None = None

    @property
    def full(self) -> bool:
        return self.level == AccessLevel.FULL

    def as_dict(self) -> dict:
        return {"level": self.level, "reason": self.reason}


def public_access(profile: Profile) -> ProfileAccess | None:
    """For a visitor who isn't signed in; None means "sign in to see this profile"."""
    # Both, as the consent wording promises: "if you agree and our team selects your profile".
    if not (profile.homepage_consent and profile.is_highlighted):
        return None
    if not Profile.objects.discoverable().filter(pk=profile.pk).exists():
        return None
    return ProfileAccess(AccessLevel.PUBLIC, Reason.SIGNED_OUT)


def member_access(viewer: Profile, profile: Profile) -> ProfileAccess:
    """For a signed-in member who may see `profile` (services.can_view_profile has passed)."""
    if viewer.pk == profile.pk:
        return ProfileAccess(AccessLevel.FULL, Reason.OWN_PROFILE)
    entitlements = entitlements_for(viewer.user)
    if entitlements.full_profile_access:
        return ProfileAccess(AccessLevel.FULL, Reason.MEMBERSHIP, entitlements)
    reason = Reason.NO_MEMBERSHIP if entitlements.is_free else Reason.PACKAGE_EXCLUDES
    return ProfileAccess(AccessLevel.LIMITED, reason, entitlements)
