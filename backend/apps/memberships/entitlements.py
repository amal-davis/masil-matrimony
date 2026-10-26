"""
What a member's membership allows, decided on the server.

A member with a current (active, in-period) subscription has that
subscription's terms; everyone else is on the Free package. Pending,
cancelled and expired subscriptions grant nothing. There is no grace period.

Only rules backed by a working feature are checked here: outgoing interests,
full profile access and contact-number access. Package benefits such as
personal messaging or "who viewed my profile" have no implementation yet, so
nothing grants them.
"""
from dataclasses import dataclass

from .models import MembershipPackage, Subscription
from .plans import PackageCode


# Packages whose current subscription unlocks the full profile page: every section
# and every photo the member's privacy settings allow (apps.profiles.access).
# Silver, Gold and Diamond list "Photo Viewing"; the assisted Platinum and Royal
# packages were confirmed by the business to include it too (October 2026).
# Contact numbers are separate: they need a contact allowance (contact_view_limit),
# which the assisted packages don't have, since their matchmaker coordinates contact.
FULL_PROFILE_PACKAGES = frozenset(
    {PackageCode.SILVER, PackageCode.GOLD, PackageCode.DIAMOND, PackageCode.PLATINUM, PackageCode.ROYAL}
)


@dataclass(frozen=True)
class Entitlements:
    package: MembershipPackage
    subscription: Subscription | None

    @property
    def is_free(self) -> bool:
        return self.subscription is None

    @property
    def full_profile_access(self) -> bool:
        """All profile sections and permitted photos, not just the basic section."""
        return self.subscription is not None and self.subscription.plan_code in FULL_PROFILE_PACKAGES

    @property
    def outgoing_interest_limit(self) -> int | None:
        """Total interests allowed while on this package; None = unlimited."""
        return self.package.outgoing_interest_limit

    @property
    def contact_view_limit(self) -> int | None:
        """Different members' numbers viewable this subscription; None = not a self-service benefit."""
        return self.subscription.contact_view_limit if self.subscription else None


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
