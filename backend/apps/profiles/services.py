"""
Profile business rules: creation, completeness, review submission, who may see
what and photo management. Match suggestions are in apps.profiles.matching.
"""
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .choices import PhotoStatus, PhotoVisibility, ProfileStatus
from .models import PartnerPreference, Profile, ProfilePhoto, generate_profile_code
from .photos import process_upload


class ProfileRuleError(Exception):
    """A request that breaks a profile rule; the message is safe to show the member."""

    def __init__(self, message, code="profile_rule"):
        super().__init__(message)
        self.message = message
        self.code = code


# --- Creation --------------------------------------------------------------


def create_profile(user, **fields) -> Profile:
    """Create the member's profile with a fresh, unique profile code."""
    for _ in range(10):
        try:
            with transaction.atomic():
                profile = Profile.objects.create(user=user, profile_code=generate_profile_code(), **fields)
                PartnerPreference.objects.create(profile=profile)
                return profile
        except IntegrityError:
            if Profile.objects.filter(user=user).exists():
                raise ProfileRuleError("You already have a profile.", code="profile_exists")
            # Profile code collision: try another.
    raise RuntimeError("Could not allocate a unique profile code.")


# --- Completeness ----------------------------------------------------------

# Fields a member needs before staff will review the profile.
REQUIRED_FOR_REVIEW = {
    "display_name": "Name",
    "gender": "Gender",
    "date_of_birth": "Date of birth",
    "height_cm": "Height",
    "marital_status": "Marital status",
    "religion": "Religion",
    "mother_tongue": "Mother tongue",
    "state": "Current state",
    "highest_education": "Highest education",
    "occupation": "Occupation",
    "about": "About me",
}

# Everything that counts towards the completion percentage: the required fields
# plus the details that make a profile genuinely useful to families.
COMPLETION_ITEMS = {
    **REQUIRED_FOR_REVIEW,
    "district": "District or city",
    "native_place": "Native place",
    "employment_type": "Employment type",
    "family_type": "Family type",
    "father_occupation": "Father's occupation",
    "mother_occupation": "Mother's occupation",
    "siblings": "Siblings",
    "partner_preference": "Partner preferences",
    "photo": "A profile photo",
}


def _has_value(profile: Profile, field: str) -> bool:
    if field == "district":
        return bool(profile.district or profile.city)
    if field == "partner_preference":
        pref = getattr(profile, "partner_preference", None)
        return bool(pref and (pref.age_min or pref.age_max or pref.religions or pref.marital_statuses))
    if field == "photo":
        return profile.photos.exclude(status=PhotoStatus.REJECTED).exists()
    value = getattr(profile, field)
    return value not in (None, "", [])


def completion(profile: Profile) -> dict:
    """Percentage complete plus what is still missing, in display order."""
    missing = [label for field, label in COMPLETION_ITEMS.items() if not _has_value(profile, field)]
    done = len(COMPLETION_ITEMS) - len(missing)
    return {"percent": round(100 * done / len(COMPLETION_ITEMS)), "missing": missing}


def missing_for_review(profile: Profile) -> list[str]:
    return [label for field, label in REQUIRED_FOR_REVIEW.items() if not _has_value(profile, field)]


def submit_for_review(profile: Profile) -> Profile:
    if profile.status not in (ProfileStatus.DRAFT, ProfileStatus.REJECTED):
        raise ProfileRuleError("This profile has already been submitted.", code="already_submitted")
    missing = missing_for_review(profile)
    if missing:
        raise ProfileRuleError(f"Please complete these first: {', '.join(missing)}.", code="incomplete")
    profile.status = ProfileStatus.PENDING_REVIEW
    profile.submitted_at = timezone.now()
    profile.review_note = ""
    profile.save(update_fields=["status", "submitted_at", "review_note", "updated_at"])
    return profile


# --- Visibility ------------------------------------------------------------


def viewer_profile(user) -> Profile | None:
    return Profile.objects.filter(user=user).first()


def can_view_profile(viewer: Profile | None, profile: Profile) -> bool:
    """Members see approved, visible profiles; everyone sees their own."""
    if viewer is not None and viewer.pk == profile.pk:
        return True
    return (
        viewer is not None
        and profile.user.is_active
        and Profile.objects.discoverable().filter(pk=profile.pk).exists()
    )


def has_accepted_interest(a: Profile, b: Profile) -> bool:
    from apps.interactions.models import Interest, InterestStatus

    return Interest.objects.filter(
        Q(sender=a, receiver=b) | Q(sender=b, receiver=a), status=InterestStatus.ACCEPTED
    ).exists()


def accepted_partner_ids(viewer: Profile) -> set[int]:
    """Profiles `viewer` has an accepted interest with, either way. One query, for lists of cards."""
    from apps.interactions.models import Interest, InterestStatus

    rows = Interest.objects.filter(Q(sender=viewer) | Q(receiver=viewer), status=InterestStatus.ACCEPTED).values_list(
        "sender_id", "receiver_id"
    )
    return {other for pair in rows for other in pair if other != viewer.pk}


# Lists of cards prefetch approved photos into this attribute (see approved_photos_prefetch).
APPROVED_PHOTOS_ATTR = "approved_photos"


def approved_photos_prefetch():
    from django.db.models import Prefetch

    return Prefetch(
        "photos", queryset=ProfilePhoto.objects.filter(status=PhotoStatus.APPROVED), to_attr=APPROVED_PHOTOS_ATTR
    )


def _approved_photos(profile: Profile) -> list[ProfilePhoto]:
    prefetched = getattr(profile, APPROVED_PHOTOS_ATTR, None)
    return list(prefetched) if prefetched is not None else list(profile.photos.filter(status=PhotoStatus.APPROVED))


def _accepted(viewer: Profile | None, profile: Profile, accepted_ids: set[int] | None) -> bool:
    if viewer is None:
        return False
    return profile.pk in accepted_ids if accepted_ids is not None else has_accepted_interest(viewer, profile)


def visible_photos(viewer: Profile | None, profile: Profile, accepted_ids: set[int] | None = None) -> list[ProfilePhoto]:
    """
    Photos `viewer` may see on `profile`: the owner sees all; others only approved ones, per privacy.
    `accepted_ids` (accepted_partner_ids) saves a query per profile in lists.
    """
    if viewer is not None and viewer.pk == profile.pk:
        return list(profile.photos.all())
    if profile.photo_visibility == PhotoVisibility.ACCEPTED and not _accepted(viewer, profile, accepted_ids):
        return []
    return _approved_photos(profile)


def photos_hidden_from(viewer: Profile | None, profile: Profile, accepted_ids: set[int] | None = None) -> bool:
    """True when the profile has approved photos the viewer isn't allowed to see."""
    if viewer is not None and viewer.pk == profile.pk:
        return False
    return (
        profile.photo_visibility == PhotoVisibility.ACCEPTED
        and bool(_approved_photos(profile))
        and not _accepted(viewer, profile, accepted_ids)
    )


def primary_photo(viewer: Profile | None, profile: Profile, accepted_ids: set[int] | None = None) -> ProfilePhoto | None:
    photos = visible_photos(viewer, profile, accepted_ids)
    return next((photo for photo in photos if photo.is_primary), photos[0] if photos else None)


# --- Photos ----------------------------------------------------------------


def add_photo(profile: Profile, upload) -> ProfilePhoto:
    """Validate and store a new photo. The first photo becomes the primary one."""
    image, width, height = process_upload(upload)  # before taking any lock: decoding is slow
    with transaction.atomic():
        locked = Profile.objects.select_for_update().get(pk=profile.pk)
        count = locked.photos.exclude(status=PhotoStatus.REJECTED).count()
        if count >= settings.PROFILE_MAX_PHOTOS:
            raise ProfileRuleError(
                f"You can have up to {settings.PROFILE_MAX_PHOTOS} photos. Remove one to add another.",
                code="photo_limit",
            )
        photo = ProfilePhoto(profile=locked, width=width, height=height, is_primary=not locked.photos.exists())
        photo.image.save("photo.jpg", image, save=False)
        try:
            photo.save()
        except Exception:
            photo.image.delete(save=False)
            raise
    return photo


def set_primary_photo(profile: Profile, photo: ProfilePhoto) -> None:
    if photo.status == PhotoStatus.REJECTED:
        raise ProfileRuleError("A rejected photo can't be your main photo.", code="photo_rejected")
    with transaction.atomic():
        Profile.objects.select_for_update().get(pk=profile.pk)
        profile.photos.filter(is_primary=True).exclude(pk=photo.pk).update(is_primary=False)
        ProfilePhoto.objects.filter(pk=photo.pk).update(is_primary=True)


def delete_photo(profile: Profile, photo: ProfilePhoto) -> None:
    """Remove a photo; if it was the main photo, the oldest remaining usable photo takes over."""
    with transaction.atomic():
        Profile.objects.select_for_update().get(pk=profile.pk)
        was_primary = photo.is_primary
        file_name = photo.image.name
        storage = photo.image.storage
        photo.delete()
        if was_primary:
            replacement = (
                profile.photos.exclude(status=PhotoStatus.REJECTED).order_by("created_at").first()
            )
            if replacement:
                ProfilePhoto.objects.filter(pk=replacement.pk).update(is_primary=True)
        # Delete the file only once the row is gone for good.
        transaction.on_commit(lambda: storage.delete(file_name))
