from django.urls import path

from .views import CurrentUserView, LoginTokenView, LogoutTokenView, RefreshTokenView

app_name = "accounts"

urlpatterns = [
    path("token/", LoginTokenView.as_view(), name="token-obtain"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    path("token/blacklist/", LogoutTokenView.as_view(), name="token-blacklist"),
    path("me/", CurrentUserView.as_view(), name="me"),
]
