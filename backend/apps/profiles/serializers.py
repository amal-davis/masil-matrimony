import re

from django.conf import settings
from rest_framework import serializers

from . import services
from .choices import (
    ALL_COMMUNITIES,
    COMMUNITIES,
    MAX_AGE,
    MIN_AGE,
    AnnualIncome,
    Diet,
    EmploymentType,
    FamilyType,
    FamilyValues,
    MaritalStatus,
    MotherTongue,
    PhotoStatus,
    PhotoVisibility,
    Religion,
)
from .models import PartnerPreference, Profile, ProfilePhoto, age_on
from .photos import signed_photo_url

# Words of letters (any script) separated by spaces, dots, apostrophes or hyphens.
NAME_PATTERN = re.compile(r"^[^\W\d_]+(?:[ .'-]+[^\W\d_]+)*\.?$")
TAG_LIMIT = 10
TAG_MAX_LENGTH = 40


def clean_tags(values, field):
    """A short list of short, distinct, trimmed strings (hobbies, languages, ...)."""
    if not isinstance(values, list):
        raise serializers.ValidationError({field: "Send a list."})
    cleaned = []
    for value in values:
        if not isinstance(value, str):
            raise serializers.ValidationError({field: "Each entry must be text."})
        value = " ".join(value.split())
        if not value:
            continue
        if len(value) > TAG_MAX_LENGTH:
            raise serializers.ValidationError({field: f"Keep each entry under {TAG_MAX_LENGTH} characters."})
        if value.lower() not in (item.lower() for item in cleaned):
            cleaned.append(value)
    if len(cleaned) > TAG_LIMIT:
        raise serializers.ValidationError({field: f"Add up to {TAG_LIMIT} entries."})
    return cleaned


def label(choices, value):
    return dict(choices.choices).get(value, "") if value else ""


# --- The member's own profile --------------------------------------------

IDENTITY_FIELDS = ("display_name", "gender", "date_of_birth")


class PartnerPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerPreference
        fields = [
            "age_min",
            "age_max",
            "height_min_cm",
            "height_max_cm",
            "marital_statuses",
            "religions",
            "communities",
            "mother_tongues",
            "diets",
            "locations",
            "education",
            "occupation",
            "notes",
            "must_haves",
        ]

    def _choice_list(self, value, allowed, field):
        value = clean_tags(value, field)
        unknown = [item for item in value if item not in allowed]
        if unknown:
            raise serializers.ValidationError(f"Unknown option: {unknown[0]}.")
        return value

    def validate_marital_statuses(self, value):
        return self._choice_list(value, MaritalStatus.values, "marital_statuses")

    def validate_religions(self, value):
        return self._choice_list(value, Religion.values, "religions")

    def validate_communities(self, value):
        return self._choice_list(value, ALL_COMMUNITIES, "communities")

    def validate_mother_tongues(self, value):
        return self._choice_list(value, MotherTongue.values, "mother_tongues")

    def validate_diets(self, value):
        return self._choice_list(value, Diet.values, "diets")

    def validate_must_haves(self, value):
        from .matching import CRITERION_KEYS

        return self._choice_list(value, CRITERION_KEYS, "must_haves")

    def validate(self, attrs):
        merged = {**{f: getattr(self.instance, f) for f in self.Meta.fields if self.instance}, **attrs}
        for low, high, name in (("age_min", "age_max", "age"), ("height_min_cm", "height_max_cm", "height")):
            if merged.get(low) and merged.get(high) and merged[low] > merged[high]:
                raise serializers.ValidationError({high: f"The maximum {name} must not be less than the minimum."})
        return attrs


class OwnProfileSerializer(serializers.ModelSerializer):
    """The signed-in member's own profile: every field, including private ones."""

    identity_locked = serializers.BooleanField(read_only=True)
    max_photos = serializers.SerializerMethodField()
    completion = serializers.SerializerMethodField()
    missing_for_review = serializers.SerializerMethodField()
    partner_preference = PartnerPreferenceSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "profile_code",
            "status",
            "review_note",
            "submitted_at",
            "identity_locked",
            "max_photos",
            "completion",
            "missing_for_review",
            "created_for",
            "display_name",
            "gender",
            "date_of_birth",
            "height_cm",
            "marital_status",
            "religion",
            "community",
            "mother_tongue",
            "country",
            "state",
            "district",
            "city",
            "native_place",
            "about",
            "highest_education",
            "education_detail",
            "institution",
            "occupation",
            "employment_type",
            "work_location",
            "annual_income",
            "income_visible",
            "family_type",
            "family_values",
            "family_location",
            "father_occupation",
            "mother_occupation",
            "siblings",
            "diet",
            "hobbies",
            "interests",
            "languages",
            "visibility",
            "photo_visibility",
            "contact_sharing",
            # The member's own consent to the public homepage. Whether staff highlighted the
            # profile (is_highlighted) is deliberately not part of the member's API.
            "homepage_consent",
            "partner_preference",
            "verification_status",
            "verification_requested_at",
            "verification_note",
            "verified_at",
        ]
        read_only_fields = [
            "profile_code", "status", "review_note", "submitted_at", "identity_locked",
            "verification_status", "verification_requested_at", "verification_note", "verified_at",
        ]

    def get_max_photos(self, profile):
        return settings.PROFILE_MAX_PHOTOS

    def get_completion(self, profile):
        return services.completion(profile)

    def get_missing_for_review(self, profile):
        return services.missing_for_review(profile)

    def to_internal_value(self, data):
        # Trim and collapse whitespace in every text value before validation.
        if hasattr(data, "items"):
            data = {
                key: (" ".join(value.split()) if key != "about" else value.strip()) if isinstance(value, str) else value
                for key, value in data.items()
            }
        return super().to_internal_value(data)

    def validate_display_name(self, value):
        if len(value) < 2 or not NAME_PATTERN.match(value):
            raise serializers.ValidationError("Use letters, spaces, dots, apostrophes or hyphens only.")
        return value

    def validate_hobbies(self, value):
        return clean_tags(value, "hobbies")

    def validate_interests(self, value):
        return clean_tags(value, "interests")

    def validate_languages(self, value):
        return clean_tags(value, "languages")

    def validate(self, attrs):
        profile = self.instance
        if profile is not None and profile.identity_locked:
            changed = [f for f in IDENTITY_FIELDS if f in attrs and attrs[f] != getattr(profile, f)]
            if changed:
                raise serializers.ValidationError(
                    {changed[0]: "This can't be changed after the profile is submitted. Please contact us to correct it."}
                )

        def current(field):
            return attrs.get(field, getattr(profile, field, None) if profile else None)

        gender, birth = current("gender"), current("date_of_birth")
        if gender and birth:
            age = age_on(birth)
            if age < MIN_AGE[gender]:
                bride_or_groom = "bride" if gender == "female" else "groom"
                raise serializers.ValidationError(
                    {"date_of_birth": f"The minimum age for a {bride_or_groom} is {MIN_AGE[gender]}."}
                )
            if age > MAX_AGE:
                raise serializers.ValidationError({"date_of_birth": "Please check the date of birth."})

        religion, community = current("religion"), current("community")
        if community and community not in COMMUNITIES.get(religion, {}):
            raise serializers.ValidationError({"community": "Choose a community that matches the religion."})
        return attrs


class CreateProfileSerializer(OwnProfileSerializer):
    """First save: who the profile is for and the identity details are required."""

    class Meta(OwnProfileSerializer.Meta):
        extra_kwargs = {field: {"required": True} for field in ("created_for", *IDENTITY_FIELDS)}


# --- Photos ---------------------------------------------------------------


class OwnPhotoSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProfilePhoto
        fields = ["id", "url", "width", "height", "is_primary", "status", "review_note", "created_at"]

    def get_url(self, photo):
        return signed_photo_url(photo, self.context.get("request"))


# --- How other members see a profile --------------------------------------


def photo_data(photo, request):
    return {"url": signed_photo_url(photo, request), "width": photo.width, "height": photo.height}


def card_data(viewer, profile, request, accepted_ids=None) -> dict:
    """
    The summary used in lists (matches, interests, shortlist). Lists pass
    `accepted_ids` (services.accepted_partner_ids) and prefetch approved photos
    (services.approved_photos_prefetch) to avoid queries per card.
    """
    photo = services.primary_photo(viewer, profile, accepted_ids)
    return {
        "profile_code": profile.profile_code,
        "display_name": profile.display_name,
        "gender": profile.gender,
        "age": profile.age,
        "height_cm": profile.height_cm,
        "marital_status": label(MaritalStatus, profile.marital_status),
        "religion": label(Religion, profile.religion),
        "community": ALL_COMMUNITIES.get(profile.community, ""),
        "education": profile.highest_education,
        "occupation": profile.occupation,
        "location": {
            "city": profile.city,
            "district": profile.district,
            "state": profile.state,
            "country": profile.country,
        },
        "photo": photo_data(photo, request) if photo else None,
        "photos_hidden": services.photos_hidden_from(viewer, profile, accepted_ids),
        # Staff verified the member's identity (apps.profiles.verification); only this yes/no is shared.
        "verified": profile.is_verified,
    }


def public_detail_data(profile, request, access) -> dict:
    """
    A visitor's view (not signed in) of a member who agreed to be shown publicly:
    exactly what that consent covers (Profile.homepage_consent), nothing else.
    """
    main = services.primary_photo(None, profile) if profile.photo_visibility == PhotoVisibility.MEMBERS else None
    photo = photo_data(main, request) if main else None
    return {
        "profile_code": profile.profile_code,
        "display_name": profile.display_name.split()[0] if profile.display_name.split() else "",
        "gender": profile.gender,
        "age": profile.age,
        "education": profile.highest_education,
        "location": {"city": profile.city, "district": profile.district, "state": profile.state, "country": ""},
        "photo": photo,
        "photos": [photo] if photo else [],
        "photos_hidden": (
            profile.photo_visibility != PhotoVisibility.MEMBERS
            and profile.photos.filter(status=PhotoStatus.APPROVED).exists()
        ),
        "access": access.as_dict(),
        "viewer": None,
    }


def detail_data(viewer, profile, request, access) -> dict:
    """
    A member's view of a profile, cut to their access level (apps.profiles.access):
    the basic section and one photo, or every section and permitted photo. Only the
    fields of that level are built: restricted data never enters the response.
    Never includes contact details or date of birth.
    """
    from apps.interactions.models import Interest, Shortlist
    from apps.interactions.services import contact_status

    is_own = viewer.pk == profile.pk
    sent = Interest.objects.filter(sender=viewer, receiver=profile).first() if not is_own else None
    received = Interest.objects.filter(sender=profile, receiver=viewer).first() if not is_own else None

    basic = {
        **card_data(viewer, profile, request),
        "mother_tongue": label(MotherTongue, profile.mother_tongue),
        "access": access.as_dict(),
        "viewer": {
            "is_own_profile": is_own,
            "interest_sent": {"id": str(sent.public_id), "status": sent.status} if sent else None,
            "interest_received": {"id": str(received.public_id), "status": received.status} if received else None,
            "shortlisted": not is_own and Shortlist.objects.filter(owner=viewer, profile=profile).exists(),
            # Whether the viewer may see this member's number (POST .../contact/ shows it).
            "contact": contact_status(viewer, profile) if not is_own else None,
        },
    }
    if not access.full:
        # The basic section: the main photo only (card_data already applied photo privacy).
        basic["photos"] = [basic["photo"]] if basic["photo"] else []
        return basic

    pref = getattr(profile, "partner_preference", None)
    return {
        **basic,
        "native_place": profile.native_place,
        "about": profile.about,
        "photos": [photo_data(photo, request) for photo in services.visible_photos(viewer, profile)
                   if is_own or photo.status == "approved"],
        "career": {
            "qualification": profile.education_detail or profile.highest_education,
            "institution": profile.institution,
            "profession": profile.occupation,
            "employment_type": label(EmploymentType, profile.employment_type),
            "work_location": profile.work_location,
            "annual_income": label(AnnualIncome, profile.annual_income) if profile.income_visible or is_own else "",
        },
        "family": {
            "type": label(FamilyType, profile.family_type),
            "values": label(FamilyValues, profile.family_values),
            "location": profile.family_location,
            "father_occupation": profile.father_occupation,
            "mother_occupation": profile.mother_occupation,
            "siblings": profile.siblings,
        },
        "lifestyle": {
            "diet": label(Diet, profile.diet),
            "hobbies": profile.hobbies,
            "interests": profile.interests,
            "languages": profile.languages,
        },
        "partner_preferences": {
            "age_range": [pref.age_min, pref.age_max] if pref and pref.age_min and pref.age_max else None,
            "height_range_cm": (
                [pref.height_min_cm, pref.height_max_cm] if pref and pref.height_min_cm and pref.height_max_cm else None
            ),
            "marital_status": ", ".join(label(MaritalStatus, v) for v in pref.marital_statuses) if pref else "",
            "religion": ", ".join(label(Religion, v) for v in pref.religions) if pref else "",
            "education": pref.education if pref else "",
            "location": pref.locations if pref else "",
            "notes": pref.notes if pref else "",
        },
    }
