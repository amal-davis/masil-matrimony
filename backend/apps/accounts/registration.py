"""
Public member registration, verified by an SMS code to the mobile number.

1. RegistrationSerializer validates the details. The view refuses a mobile
   number that already has an account (directing the visitor to log in) and an
   email address another account uses.
2. apps.accounts.otp.start_registration sends a code to the number and keeps the
   details on that code's challenge. No account exists yet, so a registration
   whose code is never entered (or never delivered) leaves nothing behind; the
   details are deleted with the challenge by purge_otp_challenges.
3. apps.accounts.otp.complete_registration checks the code and calls
   create_member: the account (mobile number verified) and its draft profile are
   created together, and the member is signed in.

- Members have no password: they always sign in with a code sent to their
  mobile number. The account gets an unusable password.
- Email is required: payment receipts are sent to it. It isn't verified with a
  link, and it is never used to sign in.
- The profile details are validated by the dashboard's own CreateProfileSerializer
  (name rules, minimum age by gender), so both routes apply the same rules.
- Saying that a number is taken lets people find out which numbers are
  registered; the per-IP throttle (API_THROTTLE_REGISTER) limits that.
"""
from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

from apps.profiles import services as profile_services
from apps.profiles.serializers import CreateProfileSerializer

from .models import User
from .phone import MobileNumberField
from .roles import Role

PROFILE_FIELDS = ("created_for", "display_name", "gender", "date_of_birth")

EMAIL_TAKEN = "Another account already uses this email address. Please use a different one."


def normalize_email(email: str) -> str:
    """The form accounts.User stores: domain and local part lower-cased (see UserManager)."""
    return User.objects.normalize_email(email.strip()).lower()


class RegistrationSerializer(serializers.Serializer):
    phone_number = MobileNumberField()
    # Where payment receipts go; never used to sign in.
    email = serializers.EmailField(
        max_length=254,
        error_messages={
            "required": "Enter your email address. We send your payment receipts there.",
            "blank": "Enter your email address. We send your payment receipts there.",
            "null": "Enter your email address. We send your payment receipts there.",
        },
    )
    accept_terms = serializers.BooleanField()
    created_for = serializers.CharField()
    display_name = serializers.CharField(max_length=60)
    gender = serializers.CharField()
    date_of_birth = serializers.DateField()

    def validate_email(self, value):
        email = normalize_email(value)
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(EMAIL_TAKEN)
        return email

    def validate_accept_terms(self, value):
        if not value:
            raise serializers.ValidationError("Please accept the Terms of Use and Privacy Policy.")
        return value

    def validate(self, attrs):
        # The profile's own rules: choices, name format, minimum age by gender.
        profile = CreateProfileSerializer(data={field: self.initial_data.get(field) for field in PROFILE_FIELDS})
        if not profile.is_valid():
            raise serializers.ValidationError(profile.errors)
        attrs.update(profile.validated_data)
        return attrs


def pending_details(validated: dict) -> dict:
    """The details kept (as JSON) on the registration's challenge until the number is verified."""
    return {
        "email": validated.get("email"),
        "created_for": validated["created_for"],
        "display_name": validated["display_name"],
        "gender": validated["gender"],
        "date_of_birth": validated["date_of_birth"].isoformat(),
    }


class DuplicateAccount(Exception):
    """Another account already has this mobile number or email address (`field`)."""

    def __init__(self, field: str):
        self.field = field
        super().__init__(field)


def create_member(phone_number: str, details: dict, *, phone_verified_at) -> User:
    """
    Create the member account and draft profile from pending_details() once the
    number is verified. Raises DuplicateAccount if the number or address was
    taken in the meantime.
    """
    email = details.get("email") or None
    names = {}
    if details["created_for"] == "self":
        # Account messages greet the account holder; when a parent or relative registers,
        # the profile name is someone else's, so the greeting stays generic.
        first, _, last = details["display_name"].partition(" ")
        names = {"first_name": first[:150], "last_name": last[:150]}

    if User.objects.filter(phone_number=phone_number).exists():
        raise DuplicateAccount("phone_number")
    if email and User.objects.filter(email=email).exists():
        raise DuplicateAccount("email")

    try:
        with transaction.atomic():
            user = User(
                email=email,
                phone_number=phone_number,
                phone_verified_at=phone_verified_at,
                role=Role.MEMBER,
                **names,
            )
            # Members sign in by SMS code only.
            user.set_unusable_password()
            user.full_clean(exclude=["password"])
            user.save()
            profile_services.create_profile(
                user,
                created_for=details["created_for"],
                display_name=details["display_name"],
                gender=details["gender"],
                date_of_birth=date.fromisoformat(details["date_of_birth"]),
            )
    except (IntegrityError, DjangoValidationError) as error:
        # Another request registered the same number or address in the meantime.
        if User.objects.filter(phone_number=phone_number).exists():
            raise DuplicateAccount("phone_number") from error
        if email and User.objects.filter(email=email).exists():
            raise DuplicateAccount("email") from error
        raise
    return user
