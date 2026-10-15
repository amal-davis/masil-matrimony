"""
Role-based DRF permission classes. Every staff endpoint must declare which
roles may use it; role checks are always enforced on the server.

Usage:
    class VerificationQueueView(APIView):
        permission_classes = [IsVerificationStaff]
"""
from rest_framework.permissions import BasePermission

from .roles import Role


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
    allowed_roles = frozenset({Role.MEMBER})


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
