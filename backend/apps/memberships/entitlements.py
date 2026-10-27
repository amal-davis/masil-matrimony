"""
What a member's membership allows, decided on the server.

A member with a current (active, in-period) subscription has that
subscription's terms; everyone else is on the Free package. Pending,
cancelled and expired subscriptions grant nothing. There is no grace period.
A subscription is only ever active after staff activated it or the payments
app confirmed a captured payment with Razorpay (apps.payments.services).

Which package includes which feature is defined once, in FEATURE_PACKAGES,
and every check (the API views and services) asks Entitlements.has(). The
numeric limits come from the subscription itself (contact numbers) or the
package (the Free interest limit), so editing a package never changes what an
existing member bought.

Features every member has, whatever their package: profile search with the
basic filters, sending and receiving interests (Free: up to the package's
total), the shortlist and match suggestions. The Free package's published
benefits don't list the shortlist or suggestions, but they were always open to
every member, so nothing is taken away here.

Two Gold and Diamond benefits are "subject to availability": the package
includes them, but the business can switch each one off for everyone
(PRIORITY_VISIBILITY_ENABLED, MATCHMAKING_ASSISTANCE_AVAILABLE). has() answers
"does the package include it"; available() answers "does it work right now".
"""
from dataclasses import dataclass

from django.conf import settings

from .models import MembershipPackage, Subscription
from .plans import PackageCode


class Feature:
    """Plan-restricted features (API codes)."""

    # Every profile section and every photo the owner's privacy allows (apps.profiles.access).
    PHOTO_VIEWING = "photo_viewing"
    # Search filters beyond the basic ones (apps.profiles.search.ADVANCED_FILTERS).
    ADVANCED_SEARCH = "advanced_search"
    # Starting a conversation (apps.interactions.messaging).
    MESSAGING = "messaging"
    # The list of members who viewed your profile (apps.interactions.profile_views).
    PROFILE_VIEWERS = "profile_viewers"
    # Asking staff to verify your identity for the Verified badge (apps.profiles.verification).
    VERIFICATION = "verification"
    # Listed ahead of other members in search and among equal matches (apps.profiles.priority).
    PRIORITY_VISIBILITY = "priority_visibility"
    # Asking for a matchmaker's help, assigned by staff (apps.memberships.assistance).
    MATCHMAKING_ASSISTANCE = "matchmaking_assistance"


# The online packages: their published benefits list each of these features.
ONLINE_PACKAGES = frozenset({PackageCode.SILVER, PackageCode.GOLD, PackageCode.DIAMOND})

FEATURE_PACKAGES = {
    # Silver, Gold and Diamond list "Photo Viewing"; the assisted Platinum and Royal
    # packages were confirmed by the business to include it too (October 2026).
    Feature.PHOTO_VIEWING: ONLINE_PACKAGES | {PackageCode.PLATINUM, PackageCode.ROYAL},
    # The assisted packages don't list these: their matchmaker searches, coordinates
    # contact and communication. Not granted to them until the business says otherwise.
    Feature.ADVANCED_SEARCH: ONLINE_PACKAGES,
    Feature.MESSAGING: ONLINE_PACKAGES,
    Feature.PROFILE_VIEWERS: ONLINE_PACKAGES,
    Feature.VERIFICATION: ONLINE_PACKAGES,
    # Gold and Diamond list "Priority Profile Visibility" and "Dedicated Matchmaking Assistance";
    # Silver doesn't. Platinum and Royal have their own matchmaker service, run offline.
    Feature.PRIORITY_VISIBILITY: frozenset({PackageCode.GOLD, PackageCode.DIAMOND}),
    Feature.MATCHMAKING_ASSISTANCE: frozenset({PackageCode.GOLD, PackageCode.DIAMOND}),
}

# Features the business can switch off platform-wide (both "subject to availability").
AVAILABILITY_SETTINGS = {
    Feature.PRIORITY_VISIBILITY: "PRIORITY_VISIBILITY_ENABLED",
    Feature.MATCHMAKING_ASSISTANCE: "MATCHMAKING_ASSISTANCE_AVAILABLE",
}


def feature_available(feature: str) -> bool:
    """Whether the platform offers the feature now (always, unless it has an availability setting)."""
    name = AVAILABILITY_SETTINGS.get(feature)
    return name is None or bool(getattr(settings, name))

# Kept for existing imports: packages whose current subscription unlocks the full profile page.
FULL_PROFILE_PACKAGES = FEATURE_PACKAGES[Feature.PHOTO_VIEWING]

UPGRADE_MESSAGES = {
    Feature.PHOTO_VIEWING: "Full profiles and photo galleries are included with paid memberships.",
    Feature.ADVANCED_SEARCH: "Advanced search filters are included with the Silver, Gold and Diamond memberships.",
    Feature.MESSAGING: "Personal messaging is included with the Silver, Gold and Diamond memberships.",
    Feature.PROFILE_VIEWERS: "Seeing who viewed your profile is included with the Silver, Gold and Diamond memberships.",
    Feature.VERIFICATION: "The Verified Profile badge is available with the Silver, Gold and Diamond memberships.",
    Feature.PRIORITY_VISIBILITY: "Priority profile visibility is included with the Gold and Diamond memberships.",
    Feature.MATCHMAKING_ASSISTANCE: "Matchmaking assistance is included with the Gold and Diamond memberships.",
}


@dataclass(frozen=True)
class Entitlements:
    package: MembershipPackage
    subscription: Subscription | None

    @property
    def is_free(self) -> bool:
        return self.subscription is None

    def has(self, feature: str) -> bool:
        return self.subscription is not None and self.subscription.plan_code in FEATURE_PACKAGES[feature]

    def available(self, feature: str) -> bool:
        """Included in the package and offered by the platform right now."""
        return self.has(feature) and feature_available(feature)

    @property
    def full_profile_access(self) -> bool:
        """All profile sections and permitted photos, not just the basic section."""
        return self.has(Feature.PHOTO_VIEWING)

    @property
    def outgoing_interest_limit(self) -> int | None:
        """Total interests allowed while on this package; None = unlimited."""
        return self.package.outgoing_interest_limit

    @property
    def contact_view_limit(self) -> int | None:
        """Different members' numbers viewable this subscription; None = not a self-service benefit."""
        return self.subscription.contact_view_limit if self.subscription else None

    @property
    def contact_views_remaining(self) -> int | None:
        limit = self.contact_view_limit
        return None if not limit else max(0, limit - self.subscription.contact_views_used)

    def as_dict(self) -> dict:
        """What the member's dashboard shows as enabled. Every value is decided here, never by the browser."""
        return {
            "package_code": self.package.code,
            "package_name": self.package.name,
            "is_paid": not self.is_free,
            "features": {
                **{feature: self.has(feature) for feature in FEATURE_PACKAGES},
                "unlimited_interests": self.outgoing_interest_limit is None,
                "contact_access": bool(self.contact_view_limit),
                # Open to every member (see the module docstring).
                "basic_search": True,
                "shortlist": True,
                "match_suggestions": True,
            },
            # Included features the business has switched off for now (shown as "currently unavailable").
            "unavailable": sorted(f for f in AVAILABILITY_SETTINGS if self.has(f) and not feature_available(f)),
            "outgoing_interest_limit": self.outgoing_interest_limit,
            "contact_view_limit": self.contact_view_limit,
            "contact_views_used": self.subscription.contact_views_used if self.contact_view_limit else None,
            "contact_views_remaining": self.contact_views_remaining,
        }


def current_subscription(user, lock=False) -> Subscription | None:
    queryset = Subscription.objects.current().filter(user=user).order_by("-ends_at")
    if lock:
        queryset = queryset.select_for_update()
    return queryset.first()


def entitlements_for(user, lock=False) -> Entitlements:
    """`lock=True` locks the current subscription row; call it inside a transaction."""
    subscription = current_subscription(user, lock=lock)
    if subscription is not None:
        return Entitlements(subscription.plan, subscription)
    return Entitlements(MembershipPackage.objects.get(code=PackageCode.FREE), None)


def upgrade_required(feature: str) -> dict:
    """The 403 body for a plan-restricted feature."""
    return {"detail": UPGRADE_MESSAGES[feature], "code": "upgrade_required", "feature": feature}
