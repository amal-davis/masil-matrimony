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

from .otp import (
    OTPDeliveryFailed,
    OTPError,
    OTPRateLimited,
    OTPUnavailable,
    request_login_code,
    verify_login_code,
)
from .password_auth import (
    LoginRateLimited,
    PasswordAuthError,
    PasswordResetRateLimited,
    PasswordResetUnavailable,
    login_with_password,
    request_password_reset,
    reset_password,
)
from .registration import RegistrationSerializer, register_member
from .serializers import (
    CurrentUserSerializer,
    DetailSerializer,
    OTPRequestedSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordLoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    TokenPairSerializer,
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
    if isinstance(error, (LoginRateLimited, PasswordResetRateLimited)):
        http_status = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(error, PasswordResetUnavailable):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
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


class RegisterView(APIView):
    """
    Create a member account (email + password) and its draft profile, and sign
    the new member in: the response is the same token pair as /auth/login/.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "register"

    @extend_schema(request=RegistrationSerializer, responses={201: TokenPairSerializer}, tags=["auth"])
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = register_member(serializer.validated_data)
        update_last_login(None, user)
        return Response(_token_pair(user), status=status.HTTP_201_CREATED)


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
