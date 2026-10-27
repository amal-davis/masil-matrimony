"""
Option lists for profile fields. Values match the website's partner search
(frontend/features/partner-search/options.ts) and quick registration form, so
the same words mean the same thing across the site.
"""
from django.db import models


class CreatedFor(models.TextChoices):
    SELF = "self", "Myself"
    SON = "son", "My son"
    DAUGHTER = "daughter", "My daughter"
    SIBLING = "sibling", "My brother or sister"
    RELATIVE = "relative", "A relative or friend"


class Gender(models.TextChoices):
    FEMALE = "female", "Female"
    MALE = "male", "Male"


# Minimum legal age of marriage in India (Prohibition of Child Marriage Act, 2006).
MIN_AGE = {Gender.FEMALE: 18, Gender.MALE: 21}
MAX_AGE = 80


class MaritalStatus(models.TextChoices):
    NEVER_MARRIED = "never_married", "Never married"
    DIVORCED = "divorced", "Divorced"
    WIDOWED = "widowed", "Widowed"
    AWAITING_DIVORCE = "awaiting_divorce", "Awaiting divorce"


class Religion(models.TextChoices):
    HINDU = "hindu", "Hindu"
    CHRISTIAN = "christian", "Christian"
    MUSLIM = "muslim", "Muslim"
    OTHER = "other", "Other"


# Communities offered for each religion; a religion with none takes no community.
COMMUNITIES = {
    Religion.HINDU: {
        "nair": "Nair",
        "ezhava": "Ezhava",
        "thiyya": "Thiyya",
        "namboothiri": "Namboothiri",
        "viswakarma": "Viswakarma",
        "nadar": "Nadar",
        "dheevara": "Dheevara",
        "hindu-other": "Other Hindu community",
    },
    Religion.CHRISTIAN: {
        "syro-malabar": "Syro-Malabar Catholic",
        "latin-catholic": "Latin Catholic",
        "syro-malankara": "Syro-Malankara Catholic",
        "malankara-orthodox": "Malankara Orthodox",
        "jacobite": "Jacobite",
        "marthoma": "Marthoma",
        "csi": "CSI",
        "pentecostal": "Pentecostal",
        "christian-other": "Other Christian denomination",
    },
    Religion.MUSLIM: {
        "sunni": "Sunni",
        "mujahid": "Mujahid",
        "muslim-other": "Other Muslim community",
    },
    Religion.OTHER: {},
}
ALL_COMMUNITIES = {code: label for options in COMMUNITIES.values() for code, label in options.items()}


class MotherTongue(models.TextChoices):
    MALAYALAM = "malayalam", "Malayalam"
    TAMIL = "tamil", "Tamil"
    KANNADA = "kannada", "Kannada"
    TULU = "tulu", "Tulu"
    KONKANI = "konkani", "Konkani"
    TELUGU = "telugu", "Telugu"
    HINDI = "hindi", "Hindi"
    OTHER = "other", "Other"


class EmploymentType(models.TextChoices):
    PRIVATE = "private", "Private sector"
    GOVERNMENT = "government", "Government / public sector"
    BUSINESS = "business", "Business"
    SELF_EMPLOYED = "self_employed", "Self-employed / professional"
    NOT_WORKING = "not_working", "Not working"
    OTHER = "other", "Other"


class AnnualIncome(models.TextChoices):
    UNDER_3L = "under_3l", "Below ₹3 lakh"
    FROM_3L = "3l_5l", "₹3–5 lakh"
    FROM_5L = "5l_10l", "₹5–10 lakh"
    FROM_10L = "10l_20l", "₹10–20 lakh"
    FROM_20L = "20l_50l", "₹20–50 lakh"
    OVER_50L = "over_50l", "Above ₹50 lakh"


class FamilyType(models.TextChoices):
    NUCLEAR = "nuclear", "Nuclear family"
    JOINT = "joint", "Joint family"
    OTHER = "other", "Other"


class FamilyValues(models.TextChoices):
    TRADITIONAL = "traditional", "Traditional"
    MODERATE = "moderate", "Moderate"
    LIBERAL = "liberal", "Liberal"


class Diet(models.TextChoices):
    VEGETARIAN = "vegetarian", "Vegetarian"
    EGGETARIAN = "eggetarian", "Eggetarian"
    NON_VEGETARIAN = "non_vegetarian", "Non-vegetarian"


class ProfileStatus(models.TextChoices):
    # Being filled in; not visible to other members.
    DRAFT = "draft", "Draft"
    # Submitted; waiting for staff review.
    PENDING_REVIEW = "pending_review", "Pending review"
    # Approved by staff and visible to members (subject to `visibility`).
    ACTIVE = "active", "Active"
    # Returned by staff with a note; the member can edit and resubmit.
    REJECTED = "rejected", "Changes requested"
    SUSPENDED = "suspended", "Suspended"


class Visibility(models.TextChoices):
    MEMBERS = "members", "Visible to members"
    HIDDEN = "hidden", "Hidden"


class PhotoVisibility(models.TextChoices):
    MEMBERS = "members", "All members"
    ACCEPTED = "accepted", "Only members whose interest I've accepted"


class ContactSharing(models.TextChoices):
    """Whether the member consents to paid members viewing their mobile number. Off until they opt in."""

    HIDDEN = "hidden", "Don't share my mobile number"
    PAID_MEMBERS = "paid_members", "Members whose package includes contact access"


class PhotoStatus(models.TextChoices):
    PENDING = "pending", "Pending review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class VerificationStatus(models.TextChoices):
    """Identity verification for the Verified badge (apps.profiles.verification). Separate from profile review."""

    NOT_REQUESTED = "not_requested", "Not requested"
    # The member asked; staff haven't decided yet.
    REQUESTED = "requested", "Awaiting verification"
    # Staff checked the member's identity document against the profile.
    VERIFIED = "verified", "Verified"
    # Staff couldn't verify; the note says why. The member may ask again.
    DECLINED = "declined", "Not verified"
