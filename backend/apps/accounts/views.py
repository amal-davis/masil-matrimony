from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from .serializers import CurrentUserSerializer


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
