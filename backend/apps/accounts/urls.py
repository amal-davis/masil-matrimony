from django.urls import path

from .views import (
    CurrentUserView,
    LoginTokenView,
    LogoutTokenView,
    OTPRequestView,
    OTPVerifyView,
    RefreshTokenView,
)

app_name = "accounts"

urlpatterns = [
    path("otp/request/", OTPRequestView.as_view(), name="otp-request"),
    path("otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    path("token/", LoginTokenView.as_view(), name="token-obtain"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    path("token/blacklist/", LogoutTokenView.as_view(), name="token-blacklist"),
    path("me/", CurrentUserView.as_view(), name="me"),
]
