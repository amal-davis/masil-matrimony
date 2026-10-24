"""
Package codes the backend knows about.

The package terms themselves (fees, tax treatment, validity, limits, benefit
copy) are MembershipPackage rows, seeded by migration 0003 and maintained in
the admin. The website's /our-packages page, the member dashboard and the
entitlement checks all read those rows; nothing else defines a price.

The codes are fixed because entitlement rules key off them: Free applies to
every member without a current paid subscription, so it is never a
Subscription plan.
"""
from django.db import models


class PackageCode(models.TextChoices):
    FREE = "free", "Free Membership"
    SILVER = "silver", "Silver Membership"
    GOLD = "gold", "Gold Membership"
    DIAMOND = "diamond", "Diamond Membership"
    PLATINUM = "platinum", "Platinum – Assisted Matchmaking"
    ROYAL = "royal", "Royal – Exclusive At-Home Matchmaking"


class PlanCode(models.TextChoices):
    """Packages a member can subscribe to (everything except Free)."""

    SILVER = PackageCode.SILVER.value, PackageCode.SILVER.label
    GOLD = PackageCode.GOLD.value, PackageCode.GOLD.label
    DIAMOND = PackageCode.DIAMOND.value, PackageCode.DIAMOND.label
    PLATINUM = PackageCode.PLATINUM.value, PackageCode.PLATINUM.label
    ROYAL = PackageCode.ROYAL.value, PackageCode.ROYAL.label
