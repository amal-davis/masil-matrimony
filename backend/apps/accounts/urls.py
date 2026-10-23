from django.urls import path

from .views import (
    CurrentUserView,
    LoginTokenView,
    LogoutTokenView,
    OTPRequestView,
    OTPVerifyView,
    PasswordLoginView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshTokenView,
    RegisterView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", PasswordLoginView.as_view(), name="login"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("password/reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("otp/request/", OTPRequestView.as_view(), name="otp-request"),
    path("otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    path("token/", LoginTokenView.as_view(), name="token-obtain"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    path("token/blacklist/", LogoutTokenView.as_view(), name="token-blacklist"),
    path("me/", CurrentUserView.as_view(), name="me"),
]
