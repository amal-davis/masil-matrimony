import uuid
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.throttling import ScopedRateThrottle

from apps.notifications import sms

from .models import PhoneOTPChallenge
from .otp import purge_expired_challenges
from .permissions import IsContentManager, IsTelecaller, IsVerificationStaff
from .roles import Role
from .views import OTPRequestView, OTPVerifyView

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


class OTPLoginApiTests(TestCase):
    REQUEST_URL = "/api/v1/auth/otp/request/"
    VERIFY_URL = "/api/v1/auth/otp/verify/"
    PHONE = "+919876543210"
    RESPONSE_FIELDS = {"challenge_id", "code_length", "expires_in", "resend_after"}

    def setUp(self):
        sms.outbox.clear()
        self.client = APIClient()
        self.member = User.objects.create_user(
            email="otp@example.com", password=PASSWORD, phone_number=self.PHONE
        )

    def request_code(self, phone=PHONE):
        return self.client.post(self.REQUEST_URL, {"phone_number": phone}, format="json")

    def verify(self, challenge_id, code):
        return self.client.post(
            self.VERIFY_URL, {"challenge_id": challenge_id, "code": code}, format="json"
        )

    def issue(self):
        """Request a code for the member; return (challenge_id, code)."""
        response = self.request_code()
        self.assertEqual(response.status_code, 202)
        return response.json()["challenge_id"], sms.outbox[-1][1]

    @staticmethod
    def wrong(code):
        return "".join(str((int(digit) + 1) % 10) for digit in code)

    @staticmethod
    def age_challenges(seconds):
        """Pretend every challenge was issued `seconds` earlier."""
        for challenge in PhoneOTPChallenge.objects.all():
            challenge.created_at -= timedelta(seconds=seconds)
            challenge.expires_at -= timedelta(seconds=seconds)
            challenge.save()

    # --- Requesting a code -------------------------------------------------

    def test_request_sends_code_to_member(self):
        response = self.request_code()
        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(set(body), self.RESPONSE_FIELDS)
        self.assertEqual(body["code_length"], settings.OTP_CODE_LENGTH)

        self.assertEqual(len(sms.outbox), 1)
        phone, code = sms.outbox[0]
        self.assertEqual(phone, self.PHONE)
        self.assertRegex(code, rf"^\d{{{settings.OTP_CODE_LENGTH}}}$")
        # The code is never returned or stored in plain text.
        self.assertNotIn(code, response.content.decode())
        self.assertNotIn(code, PhoneOTPChallenge.objects.get().code_hash)

    def test_unregistered_number_gets_same_response_without_sms(self):
        response = self.request_code("+919000000001")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(set(response.json()), self.RESPONSE_FIELDS)
        self.assertEqual(sms.outbox, [])

    def test_staff_and_inactive_accounts_get_no_sms(self):
        User.objects.create_user(
            email="staff@example.com", password=PASSWORD, phone_number="+919000000002", role=Role.ADMIN
        )
        User.objects.create_user(
            email="off@example.com", password=PASSWORD, phone_number="+919000000003", is_active=False
        )
        self.assertEqual(self.request_code("+919000000002").status_code, 202)
        self.assertEqual(self.request_code("+919000000003").status_code, 202)
        self.assertEqual(sms.outbox, [])

    def test_invalid_phone_number_is_rejected(self):
        invalid = [
            "9876543210",  # no country code
            "+0123456789",
            "+91 98765 43210",  # not normalised
            "",
            "+91987654321012345",
            "+447911123456",  # valid UK mobile: SMS login is India-only
            "+15551234567",
            "+915876543210",  # Indian mobiles start with 6-9
            "+91987654321",  # 9 digits
        ]
        for phone in invalid:
            with self.subTest(phone=phone):
                response = self.request_code(phone)
                self.assertEqual(response.status_code, 400)
                self.assertIn("phone_number", response.json())
        self.assertEqual(sms.outbox, [])

    def test_resend_cooldown(self):
        self.issue()
        response = self.request_code()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "otp_rate_limited")
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertEqual(len(sms.outbox), 1)

        self.age_challenges(settings.OTP_RESEND_COOLDOWN_SECONDS)
        self.assertEqual(self.request_code().status_code, 202)

    def test_cooldown_applies_to_unregistered_numbers_too(self):
        self.request_code("+919000000001")
        self.assertEqual(self.request_code("+919000000001").status_code, 429)

    @override_settings(OTP_MAX_REQUESTS_PER_HOUR=3)
    def test_hourly_limit_per_number(self):
        for _ in range(3):
            self.issue()
            self.age_challenges(settings.OTP_RESEND_COOLDOWN_SECONDS)
        response = self.request_code()
        self.assertEqual(response.status_code, 429)
        self.assertIn("several codes", response.json()["detail"])
        self.assertEqual(len(sms.outbox), 3)

        self.age_challenges(3600)
        self.assertEqual(self.request_code().status_code, 202)

    def test_new_code_invalidates_previous_code(self):
        old_id, old_code = self.issue()
        self.age_challenges(settings.OTP_RESEND_COOLDOWN_SECONDS)
        new_id, new_code = self.issue()

        response = self.verify(old_id, old_code)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "otp_invalid")
        self.assertEqual(self.verify(new_id, new_code).status_code, 200)

    @override_settings(SMS_PROVIDER="")
    def test_request_fails_cleanly_when_sms_not_configured(self):
        response = self.request_code()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "otp_unavailable")
        self.assertFalse(PhoneOTPChallenge.objects.exists())

    def test_provider_failure(self):
        with mock.patch.dict(sms._PROVIDERS, {"locmem": mock.Mock(side_effect=sms.SMSError("gateway down"))}):
            with self.assertLogs("apps.accounts.otp", level="ERROR") as logs:
                response = self.request_code()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "otp_delivery_failed")
        self.assertNotIn("gateway", response.json()["detail"])
        self.assertNotIn(self.PHONE, "\n".join(logs.output))
        # The failed send doesn't hold up an immediate retry.
        self.assertFalse(PhoneOTPChallenge.objects.exists())
        self.assertEqual(self.request_code().status_code, 202)

    # --- Verifying a code --------------------------------------------------

    def test_successful_verification_issues_working_tokens(self):
        self.assertIsNone(self.member.phone_verified_at)
        challenge_id, code = self.issue()

        response = self.verify(challenge_id, code)
        self.assertEqual(response.status_code, 200)
        tokens = response.json()
        self.assertEqual(set(tokens), {"access", "refresh"})

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        me = self.client.get("/api/v1/auth/me/").json()
        self.assertEqual(me["id"], str(self.member.public_id))
        self.client.credentials()

        refreshed = self.client.post(
            "/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(refreshed.status_code, 200)

        self.member.refresh_from_db()
        self.assertIsNotNone(self.member.phone_verified_at)
        self.assertIsNotNone(self.member.last_login)

    def test_incorrect_code(self):
        challenge_id, code = self.issue()
        response = self.verify(challenge_id, self.wrong(code))
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["code"], "otp_incorrect")
        self.assertEqual(body["attempts_remaining"], settings.OTP_MAX_VERIFY_ATTEMPTS - 1)
        # A wrong guess doesn't burn the challenge.
        self.assertEqual(self.verify(challenge_id, code).status_code, 200)

    def test_too_many_failed_attempts_invalidates_code(self):
        challenge_id, code = self.issue()
        for _ in range(settings.OTP_MAX_VERIFY_ATTEMPTS - 1):
            self.assertEqual(self.verify(challenge_id, self.wrong(code)).json()["code"], "otp_incorrect")
        last = self.verify(challenge_id, self.wrong(code))
        self.assertEqual(last.json()["code"], "otp_attempts_exceeded")

        # Even the right code no longer works.
        response = self.verify(challenge_id, code)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "otp_attempts_exceeded")

    def test_expired_code(self):
        challenge_id, code = self.issue()
        self.age_challenges(settings.OTP_TTL_SECONDS)
        response = self.verify(challenge_id, code)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "otp_expired")

    def test_code_cannot_be_reused(self):
        challenge_id, code = self.issue()
        self.assertEqual(self.verify(challenge_id, code).status_code, 200)
        response = self.verify(challenge_id, code)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "otp_used")

    def test_unregistered_number_can_never_verify(self):
        challenge_id = self.request_code("+919000000001").json()["challenge_id"]
        for code in ["000000", "123456", "999999"]:
            self.assertEqual(self.verify(challenge_id, code).json()["code"], "otp_incorrect")

    def test_unknown_challenge_and_malformed_input(self):
        self.assertEqual(self.verify(str(uuid.uuid4()), "123456").json()["code"], "otp_invalid")
        self.assertEqual(self.verify("not-a-uuid", "123456").status_code, 400)
        challenge_id, _ = self.issue()
        for code in ["12345", "1234567", "12a456", ""]:
            with self.subTest(code=code):
                self.assertEqual(self.verify(challenge_id, code).status_code, 400)
        # Malformed input isn't counted as a guess.
        self.assertEqual(PhoneOTPChallenge.objects.get(public_id=challenge_id).failed_attempts, 0)

    def test_account_deactivated_after_code_sent(self):
        challenge_id, code = self.issue()
        User.objects.filter(pk=self.member.pk).update(is_active=False)
        response = self.verify(challenge_id, code)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "otp_invalid")

    def test_code_is_bound_to_its_challenge(self):
        User.objects.create_user(
            email="other@example.com", password=PASSWORD, phone_number="+919000000004"
        )
        mine_id, mine_code = self.issue()
        self.request_code("+919000000004")
        _, other_code = sms.outbox[-1]
        if other_code != mine_code:  # 1-in-a-million chance the digits match
            self.assertEqual(self.verify(mine_id, other_code).json()["code"], "otp_incorrect")

    def test_endpoints_are_throttled_per_ip(self):
        cache.clear()
        self.addCleanup(cache.clear)
        rates = {"otp_request": "2/hour", "otp_verify": "2/hour"}
        with (
            mock.patch.object(OTPRequestView, "throttle_classes", [ScopedRateThrottle]),
            mock.patch.object(OTPVerifyView, "throttle_classes", [ScopedRateThrottle]),
            mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", rates),
        ):
            # Different numbers, so only the IP throttle can stop the third request.
            requests = [self.request_code(f"+91900000001{i}").status_code for i in range(3)]
            verifies = [self.verify(str(uuid.uuid4()), "123456").status_code for _ in range(3)]
        self.assertEqual(requests, [202, 202, 429])
        self.assertEqual(verifies, [400, 400, 429])

    def test_purge_removes_only_long_expired_challenges(self):
        self.issue()
        self.age_challenges(2 * 86400)
        self.request_code("+919000000001")
        self.assertEqual(purge_expired_challenges(), 1)
        self.assertEqual(PhoneOTPChallenge.objects.count(), 1)
