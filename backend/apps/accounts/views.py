from django.contrib.auth.models import update_last_login
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
from .serializers import (
    CurrentUserSerializer,
    OTPRequestedSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    TokenPairSerializer,
)


def _otp_error_response(error: OTPError) -> Response:
    if isinstance(error, OTPRateLimited):
        http_status = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(error, (OTPUnavailable, OTPDeliveryFailed)):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        http_status = status.HTTP_400_BAD_REQUEST
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

        refresh = RefreshToken.for_user(user)
        update_last_login(None, user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


class CurrentUserView(RetrieveAPIView):
    serializer_class = CurrentUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class LoginTokenView(TokenObtainPairView):
    """Exchange email + password for an access/refresh token pair."""

    throttle_scope = "auth"


class RefreshTokenView(TokenRefreshView):
    """Exchange a refresh token for a new pair; the old refresh token is blacklisted."""

    throttle_scope = "auth"


class LogoutTokenView(TokenBlacklistView):
    """Blacklist a refresh token so it can no longer be used."""

    throttle_scope = "auth"
