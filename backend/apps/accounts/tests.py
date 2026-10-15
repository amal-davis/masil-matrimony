import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory

from .permissions import IsContentManager, IsTelecaller, IsVerificationStaff
from .roles import Role

User = get_user_model()
PASSWORD = "Str0ng-test-passphrase"


class CustomUserModelTests(TestCase):
    def test_custom_user_model_is_active(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")
        self.assertIs(User, User.objects.model)

    def test_create_user_defaults_to_member(self):
        user = User.objects.create_user(email="Member@Example.com", password=PASSWORD)
        self.assertEqual(user.email, "member@example.com")
        self.assertEqual(user.role, Role.MEMBER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)

    def test_create_superuser_is_super_admin(self):
        user = User.objects.create_superuser(email="root@example.com", password=PASSWORD)
        self.assertEqual(user.role, Role.SUPER_ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_superuser_requires_password(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(email="root@example.com", password=None)

    def test_member_cannot_be_staff(self):
        with self.assertRaises(ValidationError):
            User.objects.create_user(email="m@example.com", password=PASSWORD, is_staff=True)

    def test_phone_must_be_international_format(self):
        with self.assertRaises(ValidationError):
            User.objects.create_user(email="p@example.com", password=PASSWORD, phone_number="98765")

    def test_email_is_unique_case_insensitively(self):
        User.objects.create_user(email="dup@example.com", password=PASSWORD)
        with self.assertRaises(ValidationError):
            User.objects.create_user(email="DUP@example.com", password=PASSWORD)


class RolePermissionTests(TestCase):
    def check(self, permission_class, role):
        user = User.objects.create_user(email=f"{role}-{uuid.uuid4().hex[:8]}@example.com", password=PASSWORD, role=role)
        request = APIRequestFactory().get("/")
        request.user = user
        return permission_class().has_permission(request, view=None)

    def test_role_permissions(self):
        self.assertTrue(self.check(IsVerificationStaff, Role.VERIFICATION_STAFF))
        self.assertFalse(self.check(IsVerificationStaff, Role.TELECALLER))
        self.assertTrue(self.check(IsTelecaller, Role.TELECALLER_MANAGER))
        self.assertFalse(self.check(IsTelecaller, Role.MEMBER))
        self.assertFalse(self.check(IsContentManager, Role.VERIFICATION_STAFF))
        self.assertTrue(self.check(IsContentManager, Role.SUPER_ADMIN))

    def test_inactive_user_denied(self):
        user = User.objects.create_user(
            email="off@example.com", password=PASSWORD, role=Role.ADMIN, is_active=False
        )
        request = APIRequestFactory().get("/")
        request.user = user
        self.assertFalse(IsContentManager().has_permission(request, view=None))


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="jwt@example.com", password=PASSWORD)

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)

    def test_login_with_wrong_password_fails(self):
        response = self.client.post(
            "/api/v1/auth/token/", {"email": "jwt@example.com", "password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_token_login_me_refresh_and_logout(self):
        tokens = self.client.post(
            "/api/v1/auth/token/", {"email": "jwt@example.com", "password": PASSWORD}, format="json"
        ).json()
        self.assertIn("access", tokens)
        self.assertIn("refresh", tokens)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        me = self.client.get("/api/v1/auth/me/").json()
        self.assertEqual(me["id"], str(self.user.public_id))
        self.assertEqual(me["role"], Role.MEMBER)
        self.assertNotIn("password", me)
        self.client.credentials()

        rotated = self.client.post(
            "/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(rotated.status_code, 200)

        # The original refresh token was blacklisted on rotation.
        reuse = self.client.post(
            "/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(reuse.status_code, 401)

        logout = self.client.post(
            "/api/v1/auth/token/blacklist/", {"refresh": rotated.json()["refresh"]}, format="json"
        )
        self.assertEqual(logout.status_code, 200)
