"""
Mobile numbers that members register and sign in with.

Every number is stored and compared in E.164 form (+919876543210), so the same
number typed as "98765 43210", "+91 98765-43210" or "0091 9876543210" is one
account. Only countries in SMS_ALLOWED_COUNTRY_CODES are accepted, because a
code can only be delivered where the SMS provider is set up to send (Indian
numbers need a DLT-registered template; other countries need MSG91's
international route enabled). Indian numbers must be mobiles: 10 digits starting 6-9.
"""
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework import serializers

_SEPARATORS = re.compile(r"[\s().-]")
_E164 = re.compile(r"^\+[1-9]\d{6,14}$")
_INDIA_MOBILE = re.compile(r"^\+91[6-9]\d{9}$")

INVALID = "Enter a valid mobile number with its country code, e.g. +91 98765 43210."
INVALID_INDIA = "Enter a valid 10-digit Indian mobile number, e.g. 98765 43210."
UNSUPPORTED_COUNTRY = "We can't send verification codes to numbers in this country yet."

# Longest accepted input: E.164 (16) plus room for spaces, dashes and brackets.
INPUT_MAX_LENGTH = 24


def normalize_mobile_number(value) -> str:
    """The number in E.164 form. Raises django ValidationError if it isn't an accepted mobile number."""
    if not isinstance(value, str) or len(value) > INPUT_MAX_LENGTH:
        raise ValidationError(INVALID, code="invalid")
    number = _SEPARATORS.sub("", value)
    if number.startswith("00"):
        number = f"+{number[2:]}"
    if not _E164.match(number):
        raise ValidationError(INVALID, code="invalid")
    # Calling codes are prefix-free (ITU E.164), so at most one allowed code matches.
    country = next((code for code in settings.SMS_ALLOWED_COUNTRY_CODES if number[1:].startswith(code)), None)
    if country is None:
        raise ValidationError(UNSUPPORTED_COUNTRY, code="country_not_supported")
    if country == "91" and not _INDIA_MOBILE.match(number):
        raise ValidationError(INVALID_INDIA, code="invalid")
    return number


def mask_mobile_number(number: str) -> str:
    """For logs: the last four digits only."""
    return f"***{(number or '')[-4:]}"


class MobileNumberField(serializers.CharField):
    """A mobile number in any common written form, validated and returned in E.164 form."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", INPUT_MAX_LENGTH)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_mobile_number(value)
        except ValidationError as error:
            raise serializers.ValidationError(error.messages, code=error.code) from None
