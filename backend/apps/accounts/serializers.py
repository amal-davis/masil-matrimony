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
