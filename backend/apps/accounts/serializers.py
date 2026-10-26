from django.conf import settings
from rest_framework import exceptions, serializers
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer

from .models import User
from .phone import MobileNumberField
from .roles import Role


class OTPRequestSerializer(serializers.Serializer):
    phone_number = MobileNumberField()


class OTPRequestedSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    phone_number = serializers.CharField(help_text="The number the code was sent to, in E.164 form.")
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


class RegistrationResendSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    # Optional: a corrected number for the same registration.
    phone_number = MobileNumberField(required=False)


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class StaffTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Email + password for a token pair, for staff API clients only. Members sign
    in with an SMS code; a member who still has a password from before gets the
    same answer as a wrong password.
    """

    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.role == Role.MEMBER:
            raise exceptions.AuthenticationFailed(
                self.error_messages["no_active_account"], "no_active_account"
            )
        return data


class SafeTokenRefreshSerializer(TokenRefreshSerializer):
    """
    simplejwt's refresh, but a token for an account that no longer exists (deleted,
    or issued by another database) is an invalid token (401), not a server error.
    """

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except User.DoesNotExist:
            raise InvalidToken("The account for this token no longer exists.") from None


class EmailUpdateSerializer(serializers.Serializer):
    """A member correcting their own email (where receipts go). Unique; never used to sign in."""

    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        from .registration import EMAIL_TAKEN, normalize_email

        email = normalize_email(value)
        user = self.context["user"]
        if User.objects.filter(email=email).exclude(pk=user.pk).exists():
            raise serializers.ValidationError(EMAIL_TAKEN)
        return email


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
            "phone_verified_at",
            "date_joined",
        ]
        read_only_fields = fields
