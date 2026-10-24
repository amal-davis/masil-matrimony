from django.conf import settings
from django.core.validators import RegexValidator
from rest_framework import serializers

from .models import User

# SMS login is offered for Indian mobile numbers only: +91, then 10 digits starting 6-9.
india_mobile_validator = RegexValidator(
    regex=r"^\+91[6-9]\d{9}$",
    message="Enter an Indian mobile number in international format, e.g. +919876543210.",
)


class OTPRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=16, validators=[india_mobile_validator])


class OTPRequestedSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code_length = serializers.IntegerField()
    expires_in = serializers.IntegerField(help_text="Seconds until the code expires.")
    resend_after = serializers.IntegerField(help_text="Seconds before another code may be requested.")


class OTPVerifySerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d+$", max_length=10)

    def validate_code(self, value):
        if len(value) != settings.OTP_CODE_LENGTH:
            raise serializers.ValidationError(f"Enter the {settings.OTP_CODE_LENGTH}-digit code.")
        return value


# Generous for passphrases, but bounded so a huge body can't make hashing expensive.
PASSWORD_MAX_LENGTH = 256


class PasswordLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    # Not trimmed: spaces can be part of a password.
    password = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, trim_whitespace=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.UUIDField()
    token = serializers.RegexField(r"^[0-9A-Za-z]+-[0-9A-Za-z]+$", max_length=64)
    new_password = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, trim_whitespace=False)
    new_password_confirm = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "The passwords don't match."})
        return attrs


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class RegistrationResultSerializer(serializers.Serializer):
    detail = serializers.CharField()
    email = serializers.EmailField()
    email_sent = serializers.BooleanField()
    not_sent_reason = serializers.ChoiceField(choices=["", "failed", "rate_limited"], required=False)
    delivery = serializers.ChoiceField(choices=["smtp", "console", "locmem", ""])


class VerifyEmailSerializer(serializers.Serializer):
    # django.core.signing output: URL-safe base64 segments joined by ":".
    token = serializers.RegexField(r"^[A-Za-z0-9_:-]+$", max_length=512)


class VerifiedSerializer(serializers.Serializer):
    detail = serializers.CharField()
    access = serializers.CharField(required=False)
    refresh = serializers.CharField(required=False)


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class ChangeUnverifiedEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=PASSWORD_MAX_LENGTH, trim_whitespace=False)
    new_email = serializers.EmailField(max_length=254)


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class CurrentUserSerializer(serializers.ModelSerializer):
    """The signed-in user's own account. Never used for other users."""

    id = serializers.UUIDField(source="public_id", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone_number",
            "first_name",
            "last_name",
            "role",
            "email_verified_at",
            "phone_verified_at",
            "date_joined",
        ]
        read_only_fields = fields
