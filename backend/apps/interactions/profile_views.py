"""
"Who viewed my profile?"

Recording: a view is recorded when a signed-in member opens another member's
profile page through the API (GET /profiles/<code>/, apps.profiles.views).
Nothing else counts: search results, cards in lists and the homepage don't.
Never recorded: a member looking at their own profile, visitors who aren't
signed in, and staff, who review profiles in the Django admin (staff accounts
have no member profile, so they can't open a profile through the API anyway).

Counting: one row per (viewer, profile) with the first and latest view. Opening
the page again within VISIT_GAP is the same visit (reloads, back and forward,
the page rendering twice); after that it counts as another visit.

Who is listed: only to the profile's owner, only with Feature.PROFILE_VIEWERS,
and only viewers whose own profile is currently discoverable (approved, visible
to members, active account). A member who hides their profile disappears from
everyone's viewer list, so hiding is also how a member browses unseen. Each
viewer is shown as the usual member card (card_data), which applies their
photo privacy; nothing else about them is returned.
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F, QuerySet
from django.utils import timezone

from apps.profiles.models import Profile

from .models import ProfileView

VISIT_GAP = timedelta(minutes=30)


def record_view(viewer: Profile, profile: Profile) -> None:
    if viewer.pk == profile.pk:
        return
    now = timezone.now()
    # Only counts a new visit when the last one is older than VISIT_GAP; one UPDATE, so
    # simultaneous requests can't double-count.
    updated = ProfileView.objects.filter(viewer=viewer, profile=profile, last_viewed_at__lte=now - VISIT_GAP).update(
        last_viewed_at=now, visits=F("visits") + 1
    )
    if updated or ProfileView.objects.filter(viewer=viewer, profile=profile).exists():
        return
    try:
        with transaction.atomic():
            ProfileView.objects.create(viewer=viewer, profile=profile, first_viewed_at=now, last_viewed_at=now)
    except IntegrityError:
        pass  # A simultaneous request recorded this visit.


def viewers_of(profile: Profile) -> QuerySet:
    """The owner's viewer list: most recent first, listable viewers only."""
    listable = Profile.objects.discoverable().values("pk")
    return (
        ProfileView.objects.filter(profile=profile, viewer__in=listable)
        .select_related("viewer__user")
        .order_by("-last_viewed_at", "-pk")
    )


def viewer_count(profile: Profile) -> int:
    return viewers_of(profile).count()
