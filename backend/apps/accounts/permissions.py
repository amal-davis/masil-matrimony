"""
Role-based DRF permission classes. Every staff endpoint must declare which
roles may use it; role checks are always enforced on the server.

Usage:
    class VerificationQueueView(APIView):
        permission_classes = [IsVerificationStaff]
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .roles import Role


class PhoneNotVerifiedDenied(PermissionDenied):
    default_detail = "Please log in with a code sent to your mobile number to use your account."
    default_code = "phone_not_verified"


def requires_phone_verification(user) -> bool:
    """
    True for member accounts that haven't proved their mobile number with an
    SMS code (registration and sign-in both do). Staff use the admin site instead.
    """
    return getattr(user, "role", None) == Role.MEMBER and user.phone_verified_at is None


def user_authentication_rule(user) -> bool:
    """
    SIMPLE_JWT["USER_AUTHENTICATION_RULE"]: active, and mobile-verified if a
    member. Applies when tokens are issued and on every refresh, so a session
    can't outlive a suspension or a change of mobile number.
    """
    return user is not None and user.is_active and not requires_phone_verification(user)


class HasRole(BasePermission):
    """Allow active, authenticated users whose role is in `allowed_roles`.

    Super administrators are allowed everywhere.
    """

    allowed_roles: frozenset = frozenset()

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        return user.role == Role.SUPER_ADMIN or user.role in self.allowed_roles


class IsMember(HasRole):
    """Members (and super administrators). A member must have verified their mobile number."""

    allowed_roles = frozenset({Role.MEMBER})

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if requires_phone_verification(request.user):
            # A distinct code, so the website can send the member to sign in instead of an error page.
            raise PhoneNotVerifiedDenied()
        return True


class IsAdministrator(HasRole):
    allowed_roles = frozenset({Role.ADMIN})


class IsVerificationStaff(HasRole):
    allowed_roles = frozenset({Role.ADMIN, Role.VERIFICATION_STAFF})


class IsTelecallerManager(HasRole):
    allowed_roles = frozenset({Role.ADMIN, Role.TELECALLER_MANAGER})


class IsTelecaller(HasRole):
    allowed_roles = frozenset({Role.ADMIN, Role.TELECALLER_MANAGER, Role.TELECALLER})


class IsContentManager(HasRole):
    allowed_roles = frozenset({Role.ADMIN, Role.CONTENT_MANAGER})
