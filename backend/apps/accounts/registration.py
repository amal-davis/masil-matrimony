"""
Public member registration: one request creates the account (email + password)
and the member's draft profile, so the new member can sign in straight away
and finish the profile in the dashboard.

- The password goes through AUTH_PASSWORD_VALIDATORS and Django's hasher; it is
  never stored or logged as entered. There is one password field: the website
  offers show/hide instead of a confirmation box.
- The profile details are validated by the dashboard's own CreateProfileSerializer
  (name rules, minimum age by gender), so both routes apply the same rules.
- Taken email addresses and mobile numbers are reported on the field, so people
  can sign in instead. That does reveal that an address is registered; the
  per-IP throttle (API_THROTTLE_REGISTER) limits using it to probe addresses.
"""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

from apps.profiles import services as profile_services
from apps.profiles.serializers import CreateProfileSerializer

from .models import User
from .password_auth import normalize_email
from .roles import Role
from .serializers import PASSWORD_MAX_LENGTH, india_mobile_validator

PROFILE_FIELDS = ("created_for", "display_name", "gender", "date_of_birth")

EMAIL_TAKEN = "An account already uses this email address. Sign in, or reset your password if you've forgotten it."
PHONE_TAKEN = "An account already uses this mobile number. Sign in, or contact us if you need help."


class RegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    # Not trimmed: spaces can be part of a password.
    password = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, trim_whitespace=False, write_only=True)
    phone_number = serializers.CharField(max_length=16, validators=[india_mobile_validator])
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

    def validate_phone_number(self, value):
        if User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(PHONE_TAKEN)
        return value

    def validate_accept_terms(self, value):
        if not value:
            raise serializers.ValidationError("Please accept the Terms & Conditions and Privacy Policy.")
        return value

    def validate(self, attrs):
        # The profile's own rules: choices, name format, minimum age by gender.
        profile = CreateProfileSerializer(data={field: self.initial_data.get(field) for field in PROFILE_FIELDS})
        if not profile.is_valid():
            raise serializers.ValidationError(profile.errors)
        attrs.update(profile.validated_data)

        # Checked against the details being registered, e.g. a password too like the email or name.
        candidate = User(email=attrs["email"], first_name=attrs["display_name"])
        try:
            validate_password(attrs["password"], candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": list(error.messages)})
        return attrs


def register_member(data: dict) -> User:
    """Create the member account and draft profile from RegistrationSerializer.validated_data."""
    names = {}
    if data["created_for"] == "self":
        # Account emails greet the account holder; when a parent or relative registers,
        # the profile name is someone else's, so the greeting stays generic.
        first, _, last = data["display_name"].partition(" ")
        names = {"first_name": first[:150], "last_name": last[:150]}

    try:
        with transaction.atomic():
            user = User(email=data["email"], phone_number=data["phone_number"], role=Role.MEMBER, **names)
            user.set_password(data["password"])
            user.full_clean(exclude=["password"])
            user.save()
            profile_services.create_profile(user, **{field: data[field] for field in PROFILE_FIELDS})
    except (IntegrityError, DjangoValidationError) as error:
        # Another request registered the same email or number in the meantime.
        if User.objects.filter(email=data["email"]).exists():
            raise serializers.ValidationError({"email": [EMAIL_TAKEN]}) from error
        if User.objects.filter(phone_number=data["phone_number"]).exists():
            raise serializers.ValidationError({"phone_number": [PHONE_TAKEN]}) from error
        raise
    return user
