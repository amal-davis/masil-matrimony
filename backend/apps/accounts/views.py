from django.contrib.auth.models import update_last_login
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from apps.notifications.mail import delivery_mode

from . import email_verification as verification
from .otp import (
    OTPDeliveryFailed,
    OTPError,
    OTPRateLimited,
    OTPUnavailable,
    request_login_code,
    verify_login_code,
)
from .password_auth import (
    EmailNotVerified,
    LoginRateLimited,
    PasswordAuthError,
    PasswordResetRateLimited,
    PasswordResetUnavailable,
    login_with_password,
    request_password_reset,
    reset_password,
)
from .registration import DuplicateEmail, RegistrationSerializer, register_member
from .serializers import (
    ChangeUnverifiedEmailSerializer,
    CurrentUserSerializer,
    DetailSerializer,
    OTPRequestedSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordLoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationResultSerializer,
    ResendVerificationSerializer,
    TokenPairSerializer,
    VerifiedSerializer,
    VerifyEmailSerializer,
)


def _otp_error_response(error: OTPError) -> Response:
    if isinstance(error, OTPRateLimited):
        http_status = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(error, (OTPUnavailable, OTPDeliveryFailed)):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        http_status = status.HTTP_400_BAD_REQUEST
    return _error_response(error, http_status)


def _password_error_response(error: PasswordAuthError) -> Response:
    if isinstance(error, (LoginRateLimited, PasswordResetRateLimited, verification.VerificationRateLimited)):
        http_status = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(
        error,
        (PasswordResetUnavailable, verification.VerificationUnavailable, verification.VerificationDeliveryFailed),
    ):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(error, (EmailNotVerified, verification.EmailChangeNotAllowed)):
        http_status = status.HTTP_403_FORBIDDEN
    elif isinstance(error, (verification.LinkExpired, verification.AlreadyVerified)):
        http_status = status.HTTP_410_GONE
    elif isinstance(error, verification.EmailTaken):
        http_status = status.HTTP_409_CONFLICT
    else:
        http_status = status.HTTP_400_BAD_REQUEST
    return _error_response(error, http_status)


def _error_response(error: OTPError | PasswordAuthError, http_status: int) -> Response:
    response = Response({"detail": error.message, "code": error.code, **error.extra}, status=http_status)
    if "retry_after" in error.extra:
        response["Retry-After"] = str(error.extra["retry_after"])
    return response


class OTPRequestView(APIView):
    """
    Send a login code by SMS to a member's registered mobile number (E.164).
    The response is the same whether or not the number is registered.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "otp_request"

    @extend_schema(request=OTPRequestSerializer, responses={202: OTPRequestedSerializer}, tags=["auth"])
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            issued = request_login_code(serializer.validated_data["phone_number"])
        except OTPError as error:
            return _otp_error_response(error)
        return Response(OTPRequestedSerializer(issued).data, status=status.HTTP_202_ACCEPTED)


class OTPVerifyView(APIView):
    """Exchange a challenge id and the code from the SMS for an access/refresh token pair."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "otp_verify"

    @extend_schema(request=OTPVerifySerializer, responses={200: TokenPairSerializer}, tags=["auth"])
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = verify_login_code(**serializer.validated_data)
        except OTPError as error:
            return _otp_error_response(error)

        if verification.requires_verification(user):
            return _password_error_response(EmailNotVerified())
        update_last_login(None, user)
        return Response(_token_pair(user))


def _token_pair(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class PasswordLoginView(APIView):
    """
    Website sign-in for members: exchange email + password for an access/refresh
    token pair. Every failure gets the same generic error.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "login"

    @extend_schema(request=PasswordLoginSerializer, responses={200: TokenPairSerializer}, tags=["auth"])
    def post(self, request):
        serializer = PasswordLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = login_with_password(request, **serializer.validated_data)
        except PasswordAuthError as error:
            return _password_error_response(error)
        return Response(_token_pair(user))


REGISTERED = (
    "Check your email. We've sent a verification link to {email}. "
    "Open it to verify your address, then sign in to reach your member dashboard."
)
REGISTERED_NOT_SENT = (
    "Your account has been created, but we couldn't send the verification email just now. "
    "Please request a new link in a few minutes."
)
REGISTERED_RATE_LIMITED = (
    "Your account has been created, but this address has already received several emails from us "
    "in the last hour, so we didn't send another. Please use the newest link you received, or request "
    "a new one in about an hour."
)


class RegisterView(APIView):
    """
    Create an unverified member account (email + password) and its draft
    profile, and email a verification link. No tokens: the member signs in
    after verifying. An address that is already registered gets the same 201
    answer (see registration.py); `email_sent` is false only when the email for
    a new account couldn't be handed to the mail server.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "register"

    @extend_schema(request=RegistrationSerializer, responses={201: RegistrationResultSerializer}, tags=["auth"])
    def post(self, request):
        try:
            # Checked first, so no account is created that could never be verified.
            verification.ensure_email_available()
        except verification.VerificationUnavailable as error:
            return _password_error_response(error)
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        outcome = None
        if not data["is_duplicate"]:
            try:
                outcome = verification.complete_registration(register_member(data))
            except DuplicateEmail:
                pass
        if outcome is None:
            outcome = verification.handle_duplicate_registration(data["email"])
        message = {"": REGISTERED, "failed": REGISTERED_NOT_SENT, "rate_limited": REGISTERED_RATE_LIMITED}
        body = {
            "detail": message[outcome.reason if not outcome.email_sent else ""].format(email=outcome.email),
            "email": outcome.email,
            "email_sent": outcome.email_sent,
            # Why nothing was sent: "failed" or "rate_limited" ("" when sent).
            "not_sent_reason": "" if outcome.email_sent else outcome.reason,
            # "console" in development: the email was printed by this server, not delivered.
            "delivery": delivery_mode(),
        }
        return Response(body, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    """
    Verify an account's email address from the token in an emailed link and sign
    the member in: the response carries the same token pair as /auth/login/.
    Only the request that verifies the account gets tokens; a spent, superseded
    or expired link gets an error and no session.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "email_verify"

    @extend_schema(request=VerifyEmailSerializer, responses={200: VerifiedSerializer}, tags=["auth"])
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return _password_error_response(verification.LinkInvalid())
        try:
            user = verification.verify_token(serializer.validated_data["token"])
        except PasswordAuthError as error:
            return _password_error_response(error)
        if not user.is_active:
            # Suspended while the link was in transit: verified, but no session.
            return Response({"detail": "Your email has been verified. Please contact us about your account."})
        update_last_login(None, user)
        return Response(
            {
                "detail": "Your email has been verified successfully. "
                "You can now continue to your Massil Matrimony account.",
                **_token_pair(user),
            }
        )


class ResendVerificationView(APIView):
    """
    Email a new verification link (superseding earlier ones) to an unverified
    member. The same 202 answer whether or not the address has such an account.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "email_resend"

    @extend_schema(request=ResendVerificationSerializer, responses={202: DetailSerializer}, tags=["auth"])
    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            verification.resend_verification(serializer.validated_data["email"])
        except PasswordAuthError as error:
            return _password_error_response(error)
        return Response(
            {
                "detail": "If this address has an account waiting for verification, we've sent it a new link.",
                "delivery": delivery_mode(),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ChangeUnverifiedEmailView(APIView):
    """
    Correct the email address of an account that isn't verified yet, proven by
    its password, and send a verification link to the new address.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "email_change"

    @extend_schema(
        request=ChangeUnverifiedEmailSerializer, responses={202: RegistrationResultSerializer}, tags=["auth"]
    )
    def post(self, request):
        serializer = ChangeUnverifiedEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = verification.change_unverified_email(request, data["email"], data["password"], data["new_email"])
        except PasswordAuthError as error:
            return _password_error_response(error)
        return Response(
            {
                "detail": REGISTERED.format(email=user.email),
                "email": user.email,
                "email_sent": True,
                "delivery": delivery_mode(),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetRequestView(APIView):
    """
    Email a password-reset link to a member. The response is the same whether
    or not the address is registered. Also how members who joined before
    passwords existed set their first one.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetRequestSerializer, responses={202: DetailSerializer}, tags=["auth"])
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            request_password_reset(serializer.validated_data["email"])
        except PasswordAuthError as error:
            return _password_error_response(error)
        return Response(
            {"detail": "If an account uses this email address, we've sent it a link to set a new password."},
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetConfirmView(APIView):
    """Set a new password from an emailed link. Signs the member out on every device."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "password_reset_confirm"

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: DetailSerializer}, tags=["auth"])
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            reset_password(data["uid"], data["token"], data["new_password"])
        except PasswordAuthError as error:
            return _password_error_response(error)
        except DjangoValidationError as error:
            return Response({"new_password": list(error.messages)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Your password has been changed. You can now sign in."})


class CurrentUserView(RetrieveAPIView):
    serializer_class = CurrentUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class LoginTokenView(TokenObtainPairView):
    """
    Exchange email + password for an access/refresh token pair, for any role
    (mobile apps and API clients). The website uses PasswordLoginView instead.
    """

    throttle_scope = "auth"


class RefreshTokenView(TokenRefreshView):
    """Exchange a refresh token for a new pair; the old refresh token is blacklisted."""

    throttle_scope = "auth"


class LogoutTokenView(TokenBlacklistView):
    """Blacklist a refresh token so it can no longer be used."""

    throttle_scope = "auth"
