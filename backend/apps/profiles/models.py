"""
Matrimonial profiles: personal, family, education, career, partner
preferences, photos and privacy settings. Private fields are never exposed
through public endpoints by default.

Contact details are not stored here: the member's phone number and email stay
on accounts.User and are never part of a profile response.
"""
import secrets
import uuid
from datetime import date

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel

from .choices import (
    AnnualIncome,
    ContactSharing,
    CreatedFor,
    Diet,
    EmploymentType,
    FamilyType,
    FamilyValues,
    Gender,
    MaritalStatus,
    MotherTongue,
    PhotoStatus,
    PhotoVisibility,
    ProfileStatus,
    Religion,
    Visibility,
)

HEIGHT_VALIDATORS = [MinValueValidator(120), MaxValueValidator(230)]


def generate_profile_code() -> str:
    """A short, unguessable-enough member ID such as "MM482913". Uniqueness is checked by the caller."""
    return f"MM{secrets.randbelow(900_000) + 100_000}"


def age_on(birth_date: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


class ProfileQuerySet(models.QuerySet):
    def discoverable(self):
        """Profiles other members may see: approved, not hidden, owned by an active member."""
        return self.filter(
            status=ProfileStatus.ACTIVE,
            visibility=Visibility.MEMBERS,
            user__is_active=True,
        )


class Profile(TimeStampedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    # The member ID shown to people and used in profile URLs.
    profile_code = models.CharField(max_length=12, unique=True, editable=False)
    created_for = models.CharField(max_length=16, choices=CreatedFor.choices)

    # Basic details. display_name, gender and date_of_birth are checked by staff
    # and can't be changed by the member once the profile is submitted.
    display_name = models.CharField(max_length=60)
    gender = models.CharField(max_length=8, choices=Gender.choices)
    date_of_birth = models.DateField()
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True, validators=HEIGHT_VALIDATORS)
    marital_status = models.CharField(max_length=20, choices=MaritalStatus.choices, blank=True)
    religion = models.CharField(max_length=12, choices=Religion.choices, blank=True)
    community = models.CharField(max_length=32, blank=True)
    mother_tongue = models.CharField(max_length=12, choices=MotherTongue.choices, blank=True)
    country = models.CharField(max_length=60, blank=True, default="India")
    state = models.CharField(max_length=60, blank=True)
    district = models.CharField(max_length=60, blank=True)
    city = models.CharField(max_length=60, blank=True)
    native_place = models.CharField(max_length=80, blank=True)
    about = models.TextField(max_length=2000, blank=True)

    # Education and career.
    highest_education = models.CharField(max_length=80, blank=True)
    education_detail = models.CharField(max_length=120, blank=True)
    institution = models.CharField(max_length=120, blank=True)
    occupation = models.CharField(max_length=80, blank=True)
    employment_type = models.CharField(max_length=16, choices=EmploymentType.choices, blank=True)
    work_location = models.CharField(max_length=80, blank=True)
    annual_income = models.CharField(max_length=12, choices=AnnualIncome.choices, blank=True)
    # Income is shown to other members only when the member opts in.
    income_visible = models.BooleanField(default=False)

    # Family.
    family_type = models.CharField(max_length=10, choices=FamilyType.choices, blank=True)
    family_values = models.CharField(max_length=12, choices=FamilyValues.choices, blank=True)
    family_location = models.CharField(max_length=80, blank=True)
    father_occupation = models.CharField(max_length=80, blank=True)
    mother_occupation = models.CharField(max_length=80, blank=True)
    siblings = models.CharField(max_length=160, blank=True)

    # Lifestyle. Lists of short strings, validated by the serializer.
    diet = models.CharField(max_length=16, choices=Diet.choices, blank=True)
    hobbies = models.JSONField(default=list, blank=True)
    interests = models.JSONField(default=list, blank=True)
    languages = models.JSONField(default=list, blank=True)

    # Privacy.
    visibility = models.CharField(max_length=8, choices=Visibility.choices, default=Visibility.MEMBERS)
    photo_visibility = models.CharField(
        max_length=10, choices=PhotoVisibility.choices, default=PhotoVisibility.MEMBERS
    )
    contact_sharing = models.CharField(
        max_length=12, choices=ContactSharing.choices, default=ContactSharing.HIDDEN,
        help_text="The member's consent to paid members viewing their mobile number.",
    )
    # The member's own consent to appear on the public homepage, which visitors who aren't
    # members can see. Profiles are otherwise members-only (see the privacy policy), so a
    # highlight alone never makes a profile public. Only the member can change this.
    homepage_consent = models.BooleanField(
        default=False,
        help_text="The member agreed to be featured on the public homepage (given name, age, education, "
        "location, and their main photo if their photos are visible to all members).",
    )

    # Homepage "Highlighted Profiles", chosen by staff (apps.profiles.highlights).
    is_highlighted = models.BooleanField(
        "Highlighted on homepage", default=False, db_index=True,
        help_text="Show on the homepage. Only approved, visible profiles whose member has agreed to be featured appear.",
    )
    highlight_order = models.PositiveSmallIntegerField(
        "Homepage position", default=0, help_text="Lower numbers appear first; ties show the newest approval first.",
    )

    # Review by verification staff.
    status = models.CharField(
        max_length=16, choices=ProfileStatus.choices, default=ProfileStatus.DRAFT, db_index=True
    )
    review_note = models.CharField(max_length=255, blank=True, help_text="Shown to the member.")
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = ProfileQuerySet.as_manager()

    class Meta:
        indexes = [
            # Matches: approved, visible profiles of one gender, newest first.
            models.Index(fields=["status", "visibility", "gender", "reviewed_at"]),
        ]
        permissions = [("highlight_profile", "Can highlight profiles on the homepage")]

    def __str__(self):
        return f"{self.profile_code} ({self.display_name})"

    @property
    def age(self) -> int:
        return age_on(self.date_of_birth)

    @property
    def identity_locked(self) -> bool:
        """Name, gender and date of birth are fixed once staff have the profile."""
        return self.status != ProfileStatus.DRAFT


def default_must_haves() -> list[str]:
    """
    Criteria that exclude non-matching profiles until the member says otherwise.
    These four were always applied as strict filters, so existing members keep
    the same matches. A criterion only applies once the member fills it in.
    """
    return ["age", "height", "marital_status", "religion"]


class PartnerPreference(TimeStampedModel):
    """
    What a member looks for (apps.profiles.matching). Every criterion is optional;
    those listed in `must_haves` exclude profiles that don't match, the rest
    only rank them.
    """

    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="partner_preference")
    age_min = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(18), MaxValueValidator(80)])
    age_max = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(18), MaxValueValidator(80)])
    height_min_cm = models.PositiveSmallIntegerField(null=True, blank=True, validators=HEIGHT_VALIDATORS)
    height_max_cm = models.PositiveSmallIntegerField(null=True, blank=True, validators=HEIGHT_VALIDATORS)
    marital_statuses = models.JSONField(default=list, blank=True)
    religions = models.JSONField(default=list, blank=True)
    communities = models.JSONField(default=list, blank=True)
    mother_tongues = models.JSONField(default=list, blank=True)
    diets = models.JSONField(default=list, blank=True)
    # Free text: comma-separated places, qualifications or professions (apps.profiles.matching).
    locations = models.CharField(max_length=120, blank=True)
    education = models.CharField(max_length=120, blank=True)
    occupation = models.CharField(max_length=120, blank=True)
    notes = models.TextField(max_length=500, blank=True)
    # Criterion keys (apps.profiles.matching.CRITERIA) that are requirements, not just wishes.
    must_haves = models.JSONField(default=default_must_haves, blank=True)

    def __str__(self):
        return f"Partner preference for {self.profile.profile_code}"


def photo_upload_path(instance, filename):
    # Random names only: nothing from the uploaded filename reaches the disk.
    return f"profile-photos/{instance.profile.public_id.hex}/{uuid.uuid4().hex}.jpg"


class ProfilePhoto(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="photos")
    # Always a re-encoded JPEG produced by apps.profiles.photos; never the uploaded bytes.
    image = models.FileField(upload_to=photo_upload_path, max_length=200)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    is_primary = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=PhotoStatus.choices, default=PhotoStatus.PENDING, db_index=True)
    review_note = models.CharField(max_length=255, blank=True, help_text="Shown to the member.")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # One primary photo per profile is kept by apps.profiles.services under a row
        # lock: MySQL can't enforce a conditional unique constraint.
        ordering = ["-is_primary", "created_at"]
        indexes = [models.Index(fields=["profile", "status"])]

    def __str__(self):
        return f"Photo {self.public_id} of {self.profile.profile_code}"
