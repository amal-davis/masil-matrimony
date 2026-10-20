import re
import unicodedata

from rest_framework import serializers

from .models import Enquiry

_PHONE_SEPARATORS = re.compile(r"[\s\-().]")
# E.164 allows 7-15 digits; the shortest real numbers (e.g. Tokelau, +690 7290) have 7.
_E164 = re.compile(r"^\+[1-9]\d{6,14}$")
_INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")
# Indian number written with the domestic trunk prefix, e.g. 0484 2345678 or 09876543210.
_INDIAN_TRUNK = re.compile(r"^0\d{10}$")
_NAME_PUNCTUATION = set(" .'-")

PHONE_ERROR = "Enter a valid phone number, e.g. +91 98765 43210."


def is_valid_name(value: str) -> bool:
    """Letters in any script (including Malayalam vowel signs), spaces, dots, apostrophes and hyphens."""
    if not value or not unicodedata.category(value[0]).startswith("L"):
        return False
    return all(
        unicodedata.category(char)[0] in ("L", "M") or char in _NAME_PUNCTUATION for char in value
    )


def normalise_phone(value: str) -> str:
    """
    Accept common ways of writing a phone number and return it in E.164 form.
    Numbers without a country code are treated as Indian.
    """
    number = _PHONE_SEPARATORS.sub("", value)
    if number.startswith("00"):
        number = f"+{number[2:]}"
    if number.startswith("+"):
        if not _E164.match(number):
            raise serializers.ValidationError(PHONE_ERROR)
        return number
    if _INDIAN_MOBILE.match(number):
        return f"+91{number}"
    if _INDIAN_TRUNK.match(number):
        return f"+91{number[1:]}"
    raise serializers.ValidationError(PHONE_ERROR)


class EnquiryCreateSerializer(serializers.ModelSerializer):
    """Public input for the contact form. Returns only the new enquiry's id."""

    id = serializers.UUIDField(source="public_id", read_only=True)
    name = serializers.CharField(min_length=2, max_length=100)
    phone = serializers.CharField(max_length=30)
    message = serializers.CharField(min_length=10, max_length=2000)
    # Spam trap: hidden from people, so only bots fill it in. Never stored.
    website = serializers.CharField(required=False, allow_blank=True, write_only=True, max_length=200)

    class Meta:
        model = Enquiry
        fields = ["id", "name", "email", "phone", "message", "website"]

    def validate_name(self, value: str) -> str:
        value = " ".join(value.split())
        if not is_valid_name(value):
            raise serializers.ValidationError("Use letters, spaces, dots, apostrophes or hyphens only.")
        return value

    def validate_email(self, value: str) -> str:
        local, _, domain = value.strip().rpartition("@")
        return f"{local}@{domain.lower()}"

    def validate_phone(self, value: str) -> str:
        return normalise_phone(value)

    def validate_message(self, value: str) -> str:
        return value.strip()

    def is_spam(self) -> bool:
        return bool(self.validated_data.get("website"))

    def create(self, validated_data):
        validated_data.pop("website", None)
        return super().create(validated_data)
