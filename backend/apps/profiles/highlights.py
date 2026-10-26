"""
Homepage "Highlighted Profiles": staff choose profiles in the admin; the public
GET /api/v1/profiles/highlighted/ returns them for anyone, signed in or not.

Because visitors who aren't members see the homepage, a profile appears only when
- staff highlighted it (Profile.is_highlighted; needs the highlight_profile permission),
- its member agreed to be featured publicly (Profile.homepage_consent; members only
  ever agreed to be seen by members otherwise, see the privacy policy), and
- it is discoverable: approved by staff, visibility "members", owner account active.
Highlighting never publishes or approves anything by itself.

A public card holds less than a member's card: the given name only (first word of
the profile name), age (never the date of birth), highest education, city or
district and state, and the main approved photo only when the member's photos are
visible to all members. Never contact details, surname, income or review notes.

Order: highlight_order, then most recently approved, then newest profile.
Results are read from the database on every request, so removing a highlight
takes effect on the next homepage request.
"""
from django.db.models import QuerySet

from .choices import PhotoVisibility, ProfileStatus, Visibility
from .models import Profile
from .photos import signed_photo_url
from .services import approved_photos_prefetch

MAX_HIGHLIGHTED = 12

# What has to happen before a highlighted profile can appear, by review status.
NOT_APPROVED = {
    ProfileStatus.DRAFT: "the profile is still a draft: the member must complete it and submit it for review, "
    "then staff approve it",
    ProfileStatus.PENDING_REVIEW: "the profile is waiting for review: approve it with the \"Approve\" action",
    ProfileStatus.REJECTED: "changes were requested: the member must update and resubmit it, then staff approve it",
    ProfileStatus.SUSPENDED: "the profile is suspended",
}


def highlighted_profiles(limit: int = MAX_HIGHLIGHTED) -> QuerySet:
    limit = max(1, min(int(limit), MAX_HIGHLIGHTED))
    return (
        Profile.objects.discoverable()
        .filter(is_highlighted=True, homepage_consent=True)
        .prefetch_related(approved_photos_prefetch())
        .order_by("highlight_order", "-reviewed_at", "-pk")[:limit]
    )


def why_hidden(profile: Profile) -> list[str]:
    """Why a highlighted profile isn't on the homepage, for staff. Empty when it is shown."""
    if not profile.is_highlighted:
        return []
    reasons = []
    if not profile.homepage_consent:
        reasons.append("the member hasn't agreed to be featured on the homepage (Privacy settings)")
    if profile.status != ProfileStatus.ACTIVE:
        reasons.append(NOT_APPROVED.get(profile.status, "the profile isn't approved"))
    if profile.visibility != Visibility.MEMBERS:
        reasons.append("the member has hidden their profile")
    if not profile.user.is_active:
        reasons.append("the member's account is inactive")
    return reasons


def public_card(profile: Profile, request) -> dict:
    """The fields a homepage visitor may see. Expects approved photos prefetched."""
    photo = None
    if profile.photo_visibility == PhotoVisibility.MEMBERS:
        photos = list(getattr(profile, "approved_photos", []))
        main = next((item for item in photos if item.is_primary), photos[0] if photos else None)
        if main is not None:
            photo = {"url": signed_photo_url(main, request), "width": main.width, "height": main.height}
    return {
        "profile_code": profile.profile_code,
        "given_name": profile.display_name.split()[0] if profile.display_name.split() else "",
        "gender": profile.gender,
        "age": profile.age,
        "education": profile.highest_education,
        "location": {"city": profile.city, "district": profile.district, "state": profile.state},
        "photo": photo,
    }
