from django.contrib.auth.models import update_last_login
from django.db import IntegrityError
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
    EmailTaken,
    OTPDeliveryFailed,
    OTPError,
    OTPRateLimited,
    OTPUnavailable,
    PhoneRegistered,
    RegistrationExpired,
    complete_registration,
    phone_number_registered,
    request_login_code,
    resend_registration_code,
    start_registration,
    verify_login_code,
)
from .permissions import IsMember
from .registration import EMAIL_TAKEN, RegistrationSerializer, pending_details
from .serializers import (
    CurrentUserSerializer,
    EmailUpdateSerializer,
    OTPRequestedSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    RegistrationResendSerializer,
    SafeTokenRefreshSerializer,
    StaffTokenObtainPairSerializer,
    TokenPairSerializer,
)


def _otp_error_response(error: OTPError) -> Response:
    if isinstance(error, OTPRateLimited):
        http_status = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(error, (OTPUnavailable, OTPDeliveryFailed)):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(error, (PhoneRegistered, EmailTaken)):
        http_status = status.HTTP_409_CONFLICT
    elif isinstance(error, RegistrationExpired):
        http_status = status.HTTP_410_GONE
    else:
        http_status = status.HTTP_400_BAD_REQUEST
    body = {"detail": error.message, "code": error.code, **error.extra}
    if isinstance(error, PhoneRegistered):
        body["phone_number"] = [error.message]
    response = Response(body, status=http_status)
    if "retry_after" in error.extra:
        response["Retry-After"] = str(error.extra["retry_after"])
    return response


def _token_pair(user) -> dict:
    update_last_login(None, user)
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class OTPRequestView(APIView):
    """
    Send a sign-in code by SMS to a member's registered mobile number.
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
    """Exchange a sign-in challenge id and the code from the SMS for an access/refresh token pair."""

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
        return Response(_token_pair(user))


class RegisterView(APIView):
    """
    Start a member registration: validate the details and send a code by SMS to
    the mobile number. No account is created until the code is verified
    (RegisterVerifyView). A number that already has an account gets 409 with
    code "phone_registered", so the visitor can log in instead.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "register"

    @extend_schema(request=RegistrationSerializer, responses={202: OTPRequestedSerializer}, tags=["auth"])
    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            if phone_number_registered(data["phone_number"]):
                raise PhoneRegistered()
            issued = start_registration(data["phone_number"], pending_details(data))
        except OTPError as error:
            return _otp_error_response(error)
        return Response(OTPRequestedSerializer(issued).data, status=status.HTTP_202_ACCEPTED)


class RegisterResendView(APIView):
    """
    Send a new code for a registration in progress, optionally to a corrected
    mobile number, without sending the details again. 410 when the
    registration has expired or was completed.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "register"

    @extend_schema(request=RegistrationResendSerializer, responses={202: OTPRequestedSerializer}, tags=["auth"])
    def post(self, request):
        serializer = RegistrationResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            issued = resend_registration_code(**serializer.validated_data)
        except OTPError as error:
            return _otp_error_response(error)
        return Response(OTPRequestedSerializer(issued).data, status=status.HTTP_202_ACCEPTED)


class RegisterVerifyView(APIView):
    """
    Check the registration code; on success create the member account (mobile
    verified) and draft profile and return a token pair, signing the member in.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "otp_verify"

    @extend_schema(request=OTPVerifySerializer, responses={201: TokenPairSerializer}, tags=["auth"])
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = complete_registration(**serializer.validated_data)
        except OTPError as error:
            return _otp_error_response(error)
        return Response(_token_pair(user), status=status.HTTP_201_CREATED)


class EmailUpdateView(APIView):
    """
    PATCH {"email"}: the signed-in member changes their own email address, the
    address payment receipts go to. Only ever the requester's account. Receipts
    already issued keep the address they were sent to.
    """

    permission_classes = [IsMember]
    throttle_scope = "email_update"

    @extend_schema(request=EmailUpdateSerializer, responses={200: CurrentUserSerializer}, tags=["auth"])
    def patch(self, request):
        serializer = EmailUpdateSerializer(data=request.data, context={"user": request.user})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.email = serializer.validated_data["email"]
        try:
            user.save(update_fields=["email"])
        except IntegrityError:
            return Response({"email": [EMAIL_TAKEN]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CurrentUserSerializer(user).data)


class CurrentUserView(RetrieveAPIView):
    serializer_class = CurrentUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class LoginTokenView(TokenObtainPairView):
    """
    Exchange email + password for an access/refresh token pair, for staff API
    clients. Members sign in with an SMS code (OTPRequestView, OTPVerifyView).
    """

    serializer_class = StaffTokenObtainPairSerializer
    throttle_scope = "auth"


class RefreshTokenView(TokenRefreshView):
    """Exchange a refresh token for a new pair; the old refresh token is blacklisted."""

    serializer_class = SafeTokenRefreshSerializer
    throttle_scope = "auth"


class LogoutTokenView(TokenBlacklistView):
    """Blacklist a refresh token so it can no longer be used."""

    throttle_scope = "auth"
