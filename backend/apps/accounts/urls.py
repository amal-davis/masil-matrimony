from django.urls import path

from .views import (
    CurrentUserView,
    EmailUpdateView,
    LoginTokenView,
    LogoutTokenView,
    OTPRequestView,
    OTPVerifyView,
    RefreshTokenView,
    RegisterResendView,
    RegisterVerifyView,
    RegisterView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("register/resend/", RegisterResendView.as_view(), name="register-resend"),
    path("register/verify/", RegisterVerifyView.as_view(), name="register-verify"),
    path("otp/request/", OTPRequestView.as_view(), name="otp-request"),
    path("otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    path("token/", LoginTokenView.as_view(), name="token-obtain"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    path("token/blacklist/", LogoutTokenView.as_view(), name="token-blacklist"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path("me/email/", EmailUpdateView.as_view(), name="me-email"),
]
