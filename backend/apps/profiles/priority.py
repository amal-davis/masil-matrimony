"""
Priority Profile Visibility (Gold and Diamond, "subject to platform availability").

The rule, applied only after every eligibility rule and every filter the
searching member chose:

- Search results: among the profiles that match the search, those whose owner
  currently has the feature come first; inside each group the usual order
  (most recently approved, then newest) is kept.
- Match suggestions: the match points earned on the member's own preferences
  stay the first sort key, so a better match is never placed below a weaker
  one. Priority only orders profiles with the same points.

It never adds a profile to results: hidden, unapproved, suspended or
non-matching profiles are removed before ordering, whatever the package. It
promises no number of views or matches. "Currently has the feature" is the
same rule as everywhere (an active subscription inside its period, on a
package in FEATURE_PACKAGES[PRIORITY_VISIBILITY]), so it stops when the
membership expires. With PRIORITY_VISIBILITY_ENABLED off, nobody is boosted
and the order is exactly the usual one.
"""
from django.db.models import Exists, OuterRef, QuerySet, Value
from django.db.models import BooleanField
from django.utils import timezone

from apps.memberships.entitlements import FEATURE_PACKAGES, Feature, feature_available
from apps.memberships.models import Subscription, SubscriptionStatus


def annotate_priority(queryset: QuerySet) -> QuerySet:
    """Profiles annotated with `priority` (bool): the owner has priority visibility now."""
    if not feature_available(Feature.PRIORITY_VISIBILITY):
        return queryset.annotate(priority=Value(False, output_field=BooleanField()))
    now = timezone.now()
    current = Subscription.objects.filter(
        user=OuterRef("user_id"),
        status=SubscriptionStatus.ACTIVE,
        starts_at__lte=now,
        ends_at__gt=now,
        plan_code__in=FEATURE_PACKAGES[Feature.PRIORITY_VISIBILITY],
    )
    return queryset.annotate(priority=Exists(current))
