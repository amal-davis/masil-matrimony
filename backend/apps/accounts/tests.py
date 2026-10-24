import re
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications import sms
from apps.profiles.test_utils import make_profile, make_user

from .forms import UserCreationForm
from .models import AuthAttempt, PhoneOTPChallenge
from .otp import purge_expired_challenges
from .password_auth import purge_old_attempts
from .permissions import IsContentManager, IsTelecaller, IsVerificationStaff
from .roles import Role
from .views import OTPRequestView, OTPVerifyView, PasswordLoginView, RegisterView

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
        self.user = User.objects.create_user(email="jwt@example.com", password=PASSWORD, email_verified_at=timezone.now())

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
            email="otp@example.com", password=PASSWORD, phone_number=self.PHONE, email_verified_at=timezone.now()
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


@override_settings(LOGIN_MAX_FAILURES=3, LOGIN_FAILURE_WINDOW_SECONDS=900)
class PasswordLoginApiTests(TestCase):
    URL = "/api/v1/auth/login/"
    GENERIC = {"detail": "The email address or password is incorrect.", "code": "invalid_credentials"}

    def setUp(self):
        self.client = APIClient()
        self.member = User.objects.create_user(
            email="member@example.com", password=PASSWORD, phone_number="+919876543210",
            email_verified_at=timezone.now(),
        )

    def login(self, email="member@example.com", password=PASSWORD):
        return self.client.post(self.URL, {"email": email, "password": password}, format="json")

    def test_member_signs_in_and_tokens_identify_them(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        tokens = response.json()
        self.assertEqual(set(tokens), {"access", "refresh"})
        self.member.refresh_from_db()
        self.assertIsNotNone(self.member.last_login)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        me = self.client.get("/api/v1/auth/me/").json()
        self.assertEqual(me["id"], str(self.member.public_id))
        self.assertNotIn("password", me)

    def test_email_is_matched_case_insensitively_and_trimmed(self):
        self.assertEqual(self.login(email="  Member@EXAMPLE.com ").status_code, 200)

    def test_wrong_password_and_unknown_email_get_the_same_generic_error(self):
        wrong = self.login(password="not-the-password")
        unknown = self.login(email="nobody@example.com")
        self.assertEqual((wrong.status_code, wrong.json()), (400, self.GENERIC))
        self.assertEqual((unknown.status_code, unknown.json()), (400, self.GENERIC))

    def test_staff_and_inactive_accounts_get_the_generic_error(self):
        User.objects.create_user(email="admin@example.com", password=PASSWORD, role=Role.ADMIN)
        User.objects.create_user(email="off@example.com", password=PASSWORD, is_active=False)
        self.assertEqual(self.login(email="admin@example.com").json(), self.GENERIC)
        self.assertEqual(self.login(email="off@example.com").json(), self.GENERIC)

    def test_member_without_a_password_cannot_sign_in(self):
        # Members who joined through SMS login may have no usable password.
        User.objects.create_user(email="smsonly@example.com", password=None, phone_number="+919000000001")
        self.assertEqual(self.login(email="smsonly@example.com", password="").status_code, 400)
        self.assertEqual(self.login(email="smsonly@example.com", password="anything").json(), self.GENERIC)

    def test_missing_and_malformed_input_is_rejected(self):
        response = self.client.post(self.URL, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()), {"email", "password"})
        self.assertIn("email", self.login(email="not-an-email").json())
        self.assertIn("password", self.login(password="x" * 300).json())

    def test_response_never_contains_the_password(self):
        response = self.login(password="Wrong-but-secret-123")
        self.assertNotIn("Wrong-but-secret-123", response.content.decode())

    def test_repeated_failures_lock_the_address_even_for_the_right_password(self):
        for _ in range(3):
            self.assertEqual(self.login(password="wrong").status_code, 400)
        locked = self.login()
        self.assertEqual(locked.status_code, 429)
        self.assertEqual(locked.json()["code"], "login_rate_limited")
        self.assertGreater(int(locked["Retry-After"]), 0)
        # Other members are unaffected.
        User.objects.create_user(email="other@example.com", password=PASSWORD, email_verified_at=timezone.now())
        self.assertEqual(self.login(email="other@example.com").status_code, 200)

    def test_unknown_addresses_lock_the_same_way(self):
        for _ in range(3):
            self.login(email="nobody@example.com")
        self.assertEqual(self.login(email="nobody@example.com").status_code, 429)

    def test_lock_expires_after_the_window(self):
        for _ in range(3):
            self.login(password="wrong")
        AuthAttempt.objects.update(created_at=timezone.now() - timedelta(seconds=901))
        self.assertEqual(self.login().status_code, 200)

    def test_success_clears_earlier_failures(self):
        self.login(password="wrong")
        self.login(password="wrong")
        self.assertEqual(self.login().status_code, 200)
        self.login(password="wrong")
        self.login(password="wrong")
        self.assertEqual(self.login().status_code, 200)

    def test_attempt_records_do_not_store_the_email_address(self):
        self.login(email="nobody@example.com")
        self.assertNotIn("nobody", AuthAttempt.objects.get().key)

    def test_endpoint_is_throttled_per_ip(self):
        cache.clear()
        self.addCleanup(cache.clear)
        with (
            mock.patch.object(PasswordLoginView, "throttle_classes", [ScopedRateThrottle]),
            mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"login": "2/hour"}),
        ):
            # Different addresses, so only the IP throttle can stop the third request.
            codes = [self.login(email=f"user{i}@example.com").status_code for i in range(3)]
        self.assertEqual(codes, [400, 400, 429])

    def test_logout_blacklists_the_refresh_token(self):
        refresh = self.login().json()["refresh"]
        logout = self.client.post("/api/v1/auth/token/blacklist/", {"refresh": refresh}, format="json")
        self.assertEqual(logout.status_code, 200)
        reuse = self.client.post("/api/v1/auth/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(reuse.status_code, 401)

    def test_protected_endpoints_reject_requests_without_a_token(self):
        for url in ("/api/v1/auth/me/", "/api/v1/dashboard/summary/", "/api/v1/memberships/me/"):
            self.assertEqual(self.client.get(url).status_code, 401, url)

    def test_account_created_in_the_admin_can_sign_in(self):
        # Member accounts are created with the admin's add form (there is no public sign-up yet).
        form = UserCreationForm(
            data={
                "email": "New.Member@Example.com",
                "phone_number": "+919000000002",
                "role": Role.MEMBER,
                "password1": PASSWORD,
                "password2": PASSWORD,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        # Like any member, they verify their address first (staff didn't prove they control it).
        response = self.login(email="new.member@example.com")
        self.assertEqual((response.status_code, response.json()["code"]), (403, "email_not_verified"))
        user.email_verified_at = timezone.now()
        user.save()
        self.assertEqual(self.login(email="new.member@example.com").status_code, 200)


class PasswordResetApiTests(TestCase):
    REQUEST_URL = "/api/v1/auth/password/reset/"
    CONFIRM_URL = "/api/v1/auth/password/reset/confirm/"
    NEW_PASSWORD = "Another-str0ng-passphrase"

    def setUp(self):
        mail.outbox.clear()
        self.client = APIClient()
        # Joined through SMS login: no usable password, email not yet verified.
        self.member = User.objects.create_user(
            email="member@example.com", password=None, phone_number="+919876543210", first_name="Asha"
        )

    def request_reset(self, email="member@example.com"):
        return self.client.post(self.REQUEST_URL, {"email": email}, format="json")

    def link_parts(self):
        """uid and token from the newest emailed link."""
        match = re.search(r"/reset-password#uid=([0-9a-f-]+)&token=(\S+)", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return match.group(1), match.group(2)

    def confirm(self, uid, token, password=None, confirm=None):
        password = password or self.NEW_PASSWORD
        return self.client.post(
            self.CONFIRM_URL,
            {"uid": uid, "token": token, "new_password": password, "new_password_confirm": confirm or password},
            format="json",
        )

    def login(self, password):
        return self.client.post(
            "/api/v1/auth/login/", {"email": "member@example.com", "password": password}, format="json"
        )

    def test_member_without_a_password_sets_one_by_email_and_signs_in(self):
        response = self.request_reset("Member@Example.com")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["member@example.com"])
        self.assertTrue(message.body.startswith("Hello Asha,"))
        self.assertIn("https://www.example.com/reset-password#uid=", message.body)
        # The link is only ever in the email, never in the API response.
        uid, token = self.link_parts()
        self.assertNotIn(token, response.content.decode())

        self.assertEqual(self.confirm(uid, token).status_code, 200)
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password(self.NEW_PASSWORD))
        self.assertIsNotNone(self.member.email_verified_at)
        self.assertEqual(self.login(self.NEW_PASSWORD).status_code, 200)
        # The member is told their password changed.
        self.assertIn("password was changed", mail.outbox[-1].subject)

    def test_unknown_staff_and_inactive_addresses_get_the_same_response_and_no_email(self):
        User.objects.create_user(email="admin@example.com", password=PASSWORD, role=Role.ADMIN)
        User.objects.create_user(email="off@example.com", password=PASSWORD, is_active=False)
        known = self.request_reset()
        mail.outbox.clear()
        for email in ("nobody@example.com", "admin@example.com", "off@example.com"):
            response = self.request_reset(email)
            self.assertEqual((response.status_code, response.json()), (known.status_code, known.json()))
        self.assertEqual(mail.outbox, [])

    def test_invalid_email_is_rejected(self):
        self.assertEqual(self.request_reset("not-an-email").status_code, 400)
        self.assertEqual(self.client.post(self.REQUEST_URL, {}, format="json").status_code, 400)

    @override_settings(EMAIL_PROVIDER="")
    def test_unavailable_without_an_email_provider(self):
        response = self.request_reset()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "password_reset_unavailable")
        self.assertEqual(mail.outbox, [])

    @override_settings(FRONTEND_URL="")
    def test_unavailable_without_a_website_url_for_the_link(self):
        self.assertEqual(self.request_reset().status_code, 503)

    @override_settings(PASSWORD_RESET_MAX_PER_HOUR=2)
    def test_requests_are_capped_per_address(self):
        codes = [self.request_reset().status_code for _ in range(3)]
        self.assertEqual(codes, [202, 202, 429])
        self.assertEqual(len(mail.outbox), 2)
        # Unregistered addresses are capped the same way, so the cap reveals nothing.
        codes = [self.request_reset("nobody@example.com").status_code for _ in range(3)]
        self.assertEqual(codes, [202, 202, 429])

    def test_link_works_only_once(self):
        self.request_reset()
        uid, token = self.link_parts()
        self.assertEqual(self.confirm(uid, token).status_code, 200)
        reuse = self.confirm(uid, token, password="Yet-another-passphrase-9")
        self.assertEqual(reuse.status_code, 400)
        self.assertEqual(reuse.json()["code"], "reset_link_invalid")
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password(self.NEW_PASSWORD))

    def test_link_expires(self):
        self.request_reset()
        uid, token = self.link_parts()
        later = datetime.now() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 1)
        with mock.patch.object(default_token_generator, "_now", return_value=later):
            response = self.confirm(uid, token)
        self.assertEqual(response.json()["code"], "reset_link_invalid")

    def test_link_stops_working_after_signing_in(self):
        self.member.set_password(PASSWORD)
        self.member.email_verified_at = timezone.now()
        self.member.save()
        self.request_reset()
        uid, token = self.link_parts()
        self.assertEqual(self.login(PASSWORD).status_code, 200)
        self.assertEqual(self.confirm(uid, token).json()["code"], "reset_link_invalid")

    def test_tampered_or_foreign_links_are_rejected(self):
        other = User.objects.create_user(email="other@example.com", password=PASSWORD)
        self.request_reset()
        uid, token = self.link_parts()
        self.assertEqual(self.confirm(str(other.public_id), token).json()["code"], "reset_link_invalid")
        self.assertEqual(self.confirm(str(uuid.uuid4()), token).json()["code"], "reset_link_invalid")
        self.assertEqual(self.confirm(uid, "abc-def").json()["code"], "reset_link_invalid")
        self.assertEqual(self.confirm("not-a-uuid", token).status_code, 400)

    def test_weak_or_mismatched_passwords_are_rejected(self):
        self.request_reset()
        uid, token = self.link_parts()
        weak = self.confirm(uid, token, password="12345678")
        self.assertEqual(weak.status_code, 400)
        self.assertIn("new_password", weak.json())
        mismatch = self.confirm(uid, token, password=self.NEW_PASSWORD, confirm=self.NEW_PASSWORD + "x")
        self.assertIn("new_password_confirm", mismatch.json())
        # Neither used up the link.
        self.assertEqual(self.confirm(uid, token).status_code, 200)

    def test_reset_signs_the_member_out_everywhere(self):
        self.member.set_password(PASSWORD)
        self.member.email_verified_at = timezone.now()
        self.member.save()
        refresh = self.login(PASSWORD).json()["refresh"]
        self.request_reset()
        uid, token = self.link_parts()
        self.assertEqual(self.confirm(uid, token).status_code, 200)
        reuse = self.client.post("/api/v1/auth/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(reuse.status_code, 401)

    @override_settings(LOGIN_MAX_FAILURES=2)
    def test_reset_unlocks_a_locked_address(self):
        self.login("wrong")
        self.login("wrong")
        self.assertEqual(self.login(self.NEW_PASSWORD).status_code, 429)
        self.request_reset()
        self.assertEqual(self.confirm(*self.link_parts()).status_code, 200)
        self.assertEqual(self.login(self.NEW_PASSWORD).status_code, 200)

    def test_email_failure_is_logged_without_revealing_the_account(self):
        with (
            mock.patch("apps.notifications.mail.send_mail", side_effect=OSError("connection refused")),
            self.assertLogs("apps.accounts.password_auth", level="ERROR") as logs,
        ):
            response = self.request_reset()
        self.assertEqual(response.status_code, 202)
        self.assertNotIn("token=", "\n".join(logs.output))

    def test_member_data_is_untouched(self):
        profile = make_profile(user=self.member)
        self.request_reset()
        self.assertEqual(self.confirm(*self.link_parts()).status_code, 200)
        profile.refresh_from_db()
        self.member.refresh_from_db()
        self.assertEqual(profile.user, self.member)
        self.assertEqual(self.member.phone_number, "+919876543210")

        tokens = self.login(self.NEW_PASSWORD).json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.get("/api/v1/dashboard/summary/").status_code, 200)

    def test_purge_removes_only_old_attempts(self):
        self.request_reset()
        AuthAttempt.objects.update(created_at=timezone.now() - timedelta(days=2))
        self.request_reset("nobody@example.com")
        self.assertEqual(purge_old_attempts(), 1)
        self.assertEqual(AuthAttempt.objects.count(), 1)


class RegistrationApiTests(TestCase):
    URL = "/api/v1/auth/register/"

    def setUp(self):
        self.client = APIClient()

    def payload(self, **overrides):
        data = {
            "email": "New.Member@Example.com",
            "password": PASSWORD,
            "phone_number": "+919812345678",
            "accept_terms": True,
            "created_for": "self",
            "display_name": "Anjali Menon",
            "gender": "female",
            "date_of_birth": f"{timezone.now().year - 26}-01-01",
        }
        data.update(overrides)
        return data

    def register(self, **overrides):
        return self.client.post(self.URL, self.payload(**overrides), format="json")

    def test_registration_creates_unverified_account_and_draft_profile_without_signing_in(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(set(body), {"detail", "email", "email_sent", "not_sent_reason", "delivery"})
        self.assertEqual((body["email"], body["email_sent"]), ("new.member@example.com", True))
        self.assertIn("Check your email", body["detail"])

        user = User.objects.get(email="new.member@example.com")
        self.assertEqual(user.role, Role.MEMBER)
        self.assertEqual(user.phone_number, "+919812345678")
        self.assertEqual((user.first_name, user.last_name), ("Anjali", "Menon"))
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertEqual(user.profile.status, "draft")
        self.assertEqual(user.profile.display_name, "Anjali Menon")
        self.assertIsNone(user.email_verified_at)
        self.assertIsNotNone(user.email_verification_sent_at)

    def test_registered_member_signs_in_only_after_verifying(self):
        self.register()
        credentials = {"email": "new.member@example.com", "password": PASSWORD}
        login = self.client.post("/api/v1/auth/login/", credentials, format="json")
        self.assertEqual((login.status_code, login.json()["code"]), (403, "email_not_verified"))
        self.assertNotIn("access", login.json())

        token = re.search(r"#token=([A-Za-z0-9_:-]+)", mail.outbox[-1].body).group(1)
        self.assertEqual(self.client.post("/api/v1/auth/email/verify/", {"token": token}, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/login/", credentials, format="json").status_code, 200)

    def test_profile_for_a_relative_keeps_the_account_greeting_generic(self):
        self.register(created_for="son", gender="male", display_name="Arun Kumar")
        user = User.objects.get(email="new.member@example.com")
        self.assertEqual((user.first_name, user.last_name), ("", ""))
        self.assertEqual(user.profile.display_name, "Arun Kumar")

    def test_weak_passwords_are_rejected(self):
        for password in ("short1", "1234567890", "password123", "new.member@example.com"):
            response = self.register(password=password)
            self.assertEqual(response.status_code, 400, password)
            self.assertIn("password", response.json())
        self.assertFalse(User.objects.exists())

    def test_profile_rules_apply(self):
        too_young = f"{timezone.now().year - 19}-01-01"
        self.assertIn("date_of_birth", self.register(gender="male", date_of_birth=too_young).json())
        self.assertIn("display_name", self.register(display_name="X1").json())
        self.assertIn("created_for", self.register(created_for="friend").json())
        self.assertFalse(User.objects.exists())

    def test_terms_must_be_accepted_and_inputs_are_checked(self):
        self.assertIn("accept_terms", self.register(accept_terms=False).json())
        self.assertIn("email", self.register(email="not-an-email").json())
        self.assertIn("phone_number", self.register(phone_number="+911234567890").json())
        missing = self.client.post(self.URL, {}, format="json").json()
        self.assertTrue({"email", "password", "phone_number", "display_name"} <= set(missing))
        self.assertFalse(User.objects.exists())

    def test_password_is_never_returned(self):
        response = self.register(password="Wrong-but-secret-123", email="bad")
        self.assertNotIn("Wrong-but-secret-123", response.content.decode())

    def test_endpoint_is_throttled_per_ip(self):
        cache.clear()
        self.addCleanup(cache.clear)
        with (
            mock.patch.object(RegisterView, "throttle_classes", [ScopedRateThrottle]),
            mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"register": "2/hour"}),
        ):
            codes = [self.register(email="bad").status_code for _ in range(3)]
        self.assertEqual(codes, [400, 400, 429])


def token_from(message) -> str:
    """The verification token in an emailed link (the part after #token=)."""
    return re.search(r"#token=([A-Za-z0-9_:-]+)", message.body).group(1)


class EmailVerificationTests(TestCase):
    VERIFY = "/api/v1/auth/email/verify/"
    RESEND = "/api/v1/auth/email/resend/"
    CHANGE = "/api/v1/auth/email/change/"
    REGISTER = "/api/v1/auth/register/"
    LOGIN = "/api/v1/auth/login/"

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def register(self, **overrides):
        data = {
            "email": "asha@example.com",
            "password": PASSWORD,
            "phone_number": "+919812345670",
            "accept_terms": True,
            "created_for": "self",
            "display_name": "Asha Nair",
            "gender": "female",
            "date_of_birth": f"{timezone.now().year - 26}-01-01",
            **overrides,
        }
        return self.client.post(self.REGISTER, data, format="json")

    def verify(self, token):
        return self.client.post(self.VERIFY, {"token": token}, format="json")

    def login(self, email="asha@example.com", password=PASSWORD):
        return self.client.post(self.LOGIN, {"email": email, "password": password}, format="json")

    def user(self, email="asha@example.com"):
        return User.objects.get(email=email)

    # --- the email -------------------------------------------------------

    def test_registration_sends_a_branded_email_with_an_absolute_link(self):
        response = self.register()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["asha@example.com"])
        self.assertEqual(message.subject, "Verify your email address for Massil Matrimony")
        self.assertIn("https://www.example.com/verify-email#token=", message.body)
        self.assertIn("24 hours", message.body)
        self.assertIn("didn't create", message.body)
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn("Verify Email Address", html)
        self.assertIn(token_from(message), html)
        # No support address is configured, so the email points to the contact page rather than inventing one.
        self.assertIn("https://www.example.com/contact", message.body)
        # The token is never in the API response.
        self.assertNotIn(token_from(message), response.content.decode())

    @override_settings(SUPPORT_EMAIL="help@massil.example")
    def test_configured_support_address_is_used(self):
        self.register()
        self.assertIn("help@massil.example", mail.outbox[0].body)

    # --- verifying ---------------------------------------------------------

    def test_valid_link_verifies_only_that_account(self):
        self.register()
        self.register(email="other@example.com", phone_number="+919812345671")
        response = self.verify(token_from(mail.outbox[0]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("verified successfully", response.json()["detail"])
        # The verifying request is signed in, as the member whose link it was.
        tokens = response.json()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(client.get("/api/v1/auth/me/").json()["email"], "asha@example.com")
        self.assertEqual(client.get("/api/v1/profiles/me/").status_code, 200)
        self.assertIsNotNone(self.user().email_verified_at)
        self.assertIsNone(self.user("other@example.com").email_verified_at)

    def test_link_works_once(self):
        self.register()
        token = token_from(mail.outbox[0])
        self.assertEqual(self.verify(token).status_code, 200)
        verified_at = self.user().email_verified_at
        again = self.verify(token)
        self.assertEqual((again.status_code, again.json()["code"]), (410, "email_already_verified"))
        # A spent link never signs anyone in again.
        self.assertNotIn("access", again.json())
        self.assertNotIn("refresh", again.json())
        self.assertEqual(self.user().email_verified_at, verified_at)

    @override_settings(EMAIL_VERIFICATION_TIMEOUT=60)
    def test_expired_link_is_rejected(self):
        self.register()
        token = token_from(mail.outbox[0])
        with mock.patch("django.core.signing.time.time", return_value=time.time() + 61):
            response = self.verify(token)
        self.assertEqual((response.status_code, response.json()["code"]), (410, "verification_link_expired"))
        self.assertIsNone(self.user().email_verified_at)

    def test_invalid_and_tampered_links_are_rejected(self):
        self.register()
        token = token_from(mail.outbox[0])
        for bad in ("", "nonsense", token[:-2] + "xx", token + "a", "a" * 600, "<script>"):
            with self.subTest(token=bad):
                response = self.verify(bad)
                self.assertEqual((response.status_code, response.json()["code"]), (400, "verification_link_invalid"))
        self.assertIsNone(self.user().email_verified_at)

    def test_resending_supersedes_earlier_links(self):
        self.register()
        first = token_from(mail.outbox[0])
        self.assertEqual(self.client.post(self.RESEND, {"email": "ASHA@example.com"}, format="json").status_code, 202)
        second = token_from(mail.outbox[1])
        self.assertNotEqual(first, second)
        self.assertEqual(self.verify(first).json()["code"], "verification_link_invalid")
        self.assertEqual(self.verify(second).status_code, 200)

    # --- resending -----------------------------------------------------------

    @override_settings(EMAIL_VERIFICATION_MAX_PER_HOUR=3)
    def test_resending_is_capped_per_address(self):
        self.register()  # the first of three
        codes = [self.client.post(self.RESEND, {"email": "asha@example.com"}, format="json").status_code for _ in range(3)]
        self.assertEqual(codes, [202, 202, 429])
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(User.objects.filter(email="asha@example.com").count(), 1)

    @override_settings(EMAIL_VERIFICATION_MAX_PER_HOUR=2)
    def test_resend_answers_the_same_for_unknown_and_verified_addresses_and_sends_nothing(self):
        make_user(email_verified_at=timezone.now())
        for email in ("nobody@example.com", User.objects.get().email):
            with self.subTest(email=email):
                response = self.client.post(self.RESEND, {"email": email}, format="json")
                self.assertEqual(response.status_code, 202)
        self.assertEqual(mail.outbox, [])
        # Unknown addresses are capped too, so the cap reveals nothing.
        for _ in range(2):
            last = self.client.post(self.RESEND, {"email": "nobody@example.com"}, format="json")
        self.assertEqual(last.status_code, 429)

    def test_resend_endpoint_is_throttled_per_ip(self):
        rates = {**ScopedRateThrottle.THROTTLE_RATES, "email_resend": "2/hour"}
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", rates), mock.patch(
            "apps.accounts.views.ResendVerificationView.throttle_classes", [ScopedRateThrottle]
        ):
            codes = [
                self.client.post(self.RESEND, {"email": f"x{i}@example.com"}, format="json").status_code
                for i in range(3)
            ]
        self.assertEqual(codes, [202, 202, 429])

    # --- delivery problems ---------------------------------------------------------

    def test_delivery_failure_on_registration_is_reported_honestly(self):
        with mock.patch("django.core.mail.backends.locmem.EmailBackend.send_messages", side_effect=OSError("down")):
            with self.assertLogs("apps.accounts.email_verification", "ERROR") as logs:
                response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertIs(response.json()["email_sent"], False)
        self.assertIn("couldn't send", response.json()["detail"])
        self.assertIsNone(self.user().email_verified_at)
        # The failed link was never stored, and nothing secret was logged.
        self.assertIsNone(self.user().email_verification_sent_at)
        self.assertNotIn("token", " ".join(logs.output))
        # Retrying works once delivery does.
        self.assertEqual(self.client.post(self.RESEND, {"email": "asha@example.com"}, format="json").status_code, 202)
        self.assertEqual(self.verify(token_from(mail.outbox[-1])).status_code, 200)

    def test_delivery_failure_on_resend_is_reported(self):
        self.register()
        with mock.patch("django.core.mail.backends.locmem.EmailBackend.send_messages", side_effect=OSError("down")):
            response = self.client.post(self.RESEND, {"email": "asha@example.com"}, format="json")
        self.assertEqual((response.status_code, response.json()["code"]), (503, "verification_email_failed"))
        # The link from the earlier, delivered email still works.
        self.assertEqual(self.verify(token_from(mail.outbox[0])).status_code, 200)

    @override_settings(EMAIL_PROVIDER="")
    def test_registration_is_refused_without_email_so_no_unverifiable_account_is_created(self):
        response = self.register()
        self.assertEqual((response.status_code, response.json()["code"]), (503, "email_unavailable"))
        self.assertFalse(User.objects.exists())

    # --- duplicates ---------------------------------------------------------

    def test_duplicate_registration_looks_like_a_new_one_and_changes_nothing(self):
        self.register()
        original = self.user()
        response = self.register(email="Asha@Example.com", password="Another-str0ng-pass", phone_number="+919812345679")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.json()), {"detail", "email", "email_sent", "not_sent_reason", "delivery"})
        self.assertEqual(User.objects.count(), 1)
        user = self.user()
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.phone_number, original.phone_number)
        # Unverified: its owner gets a new link (superseding the first).
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(self.verify(token_from(mail.outbox[1])).status_code, 200)

    def test_duplicate_of_a_verified_account_notifies_its_owner_only(self):
        self.register()
        self.verify(token_from(mail.outbox[0]))
        response = self.register(password="Another-str0ng-pass")
        self.assertEqual(response.status_code, 201)
        notice = mail.outbox[-1]
        self.assertEqual(notice.to, ["asha@example.com"])
        self.assertIn("already have", notice.subject)
        self.assertNotIn("#token=", notice.body)
        self.assertTrue(self.user().check_password(PASSWORD))

    def test_taken_mobile_with_a_new_email_is_still_reported(self):
        self.register()
        response = self.register(email="fresh@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone_number", response.json())
        self.assertEqual(User.objects.count(), 1)

    def test_simultaneous_registration_of_the_same_address_is_safe(self):
        from .registration import DuplicateEmail, RegistrationSerializer, register_member

        serializer = RegistrationSerializer(data={
            "email": "asha@example.com", "password": PASSWORD, "phone_number": "+919812345670", "accept_terms": True,
            "created_for": "self", "display_name": "Asha Nair", "gender": "female",
            "date_of_birth": f"{timezone.now().year - 26}-01-01",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        # Both requests passed validation before either saved.
        register_member(serializer.validated_data)
        with self.assertRaises(DuplicateEmail):
            register_member(serializer.validated_data)
        self.assertEqual(User.objects.count(), 1)

    # --- blocking unverified accounts ---------------------------------------------------------

    def test_unverified_member_cannot_sign_in_by_password_token_or_sms(self):
        self.register()
        login = self.login()
        self.assertEqual((login.status_code, login.json()["code"]), (403, "email_not_verified"))
        # A wrong password still gets the generic error, so the state isn't revealed without it.
        self.assertEqual(self.login(password="wrong").json()["code"], "invalid_credentials")
        api_token = self.client.post("/api/v1/auth/token/", {"email": "asha@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(api_token.status_code, 401)

        sms.outbox.clear()
        with override_settings(SMS_PROVIDER="locmem"):
            challenge = self.client.post("/api/v1/auth/otp/request/", {"phone_number": "+919812345670"}, format="json")
            code = sms.outbox[-1][1]
            otp = self.client.post(
                "/api/v1/auth/otp/verify/",
                {"challenge_id": challenge.json()["challenge_id"], "code": code},
                format="json",
            )
        self.assertEqual((otp.status_code, otp.json()["code"]), (403, "email_not_verified"))

    def test_unverified_member_cannot_use_member_apis(self):
        self.register()
        client = APIClient()
        client.force_authenticate(self.user())
        for url in ("/api/v1/profiles/me/", "/api/v1/dashboard/summary/", "/api/v1/memberships/me/", "/api/v1/interests/sent/"):
            with self.subTest(url=url):
                response = client.get(url)
                self.assertEqual((response.status_code, response.json()["code"]), (403, "email_not_verified"))

    def test_existing_session_stops_at_refresh_until_verified(self):
        # An account signed in before verification became mandatory.
        user = make_user(email_verified_at=None)
        refresh = str(RefreshToken.for_user(user))
        self.assertEqual(self.client.post("/api/v1/auth/token/refresh/", {"refresh": refresh}, format="json").status_code, 401)

    def test_suspension_is_separate_from_verification(self):
        self.register()
        self.verify(token_from(mail.outbox[0]))
        User.objects.filter(email="asha@example.com").update(is_active=False)
        self.assertEqual(self.login().json()["code"], "invalid_credentials")
        self.assertIsNotNone(self.user().email_verified_at)

    def test_verified_member_uses_the_normal_flow(self):
        self.register()
        self.verify(token_from(mail.outbox[0]))
        tokens = self.login().json()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(client.get("/api/v1/profiles/me/").status_code, 200)
        refreshed = self.client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(refreshed.status_code, 200)

    def test_staff_accounts_are_not_affected(self):
        staff = User.objects.create_user(email="staff@example.com", password=PASSWORD, role=Role.ADMIN, is_staff=True)
        self.assertIsNone(staff.email_verified_at)
        self.client.force_login(staff)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    # --- correcting the address ---------------------------------------------------------

    def test_wrong_address_can_be_corrected_with_the_password(self):
        self.register(email="asha@exmaple.com")
        old_token = token_from(mail.outbox[0])
        response = self.client.post(
            self.CHANGE, {"email": "asha@exmaple.com", "password": PASSWORD, "new_email": "Asha@Example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["email"], "asha@example.com")
        self.assertEqual(mail.outbox[-1].to, ["asha@example.com"])
        # The link sent to the mistyped address no longer works.
        self.assertEqual(self.verify(old_token).json()["code"], "verification_link_invalid")
        self.assertEqual(self.verify(token_from(mail.outbox[-1])).status_code, 200)
        self.assertEqual(self.login().status_code, 200)

    def test_correction_needs_the_password_and_an_unverified_account(self):
        self.register()
        wrong = self.client.post(
            self.CHANGE, {"email": "asha@example.com", "password": "wrong", "new_email": "attacker@example.com"}, format="json"
        )
        self.assertEqual((wrong.status_code, wrong.json()["code"]), (400, "invalid_credentials"))
        self.assertEqual(self.user().email, "asha@example.com")

        self.verify(token_from(mail.outbox[0]))
        verified = self.client.post(
            self.CHANGE, {"email": "asha@example.com", "password": PASSWORD, "new_email": "new@example.com"}, format="json"
        )
        self.assertEqual((verified.status_code, verified.json()["code"]), (403, "email_change_not_allowed"))

    def test_correction_cannot_take_an_address_in_use(self):
        self.register()
        make_user(email_verified_at=timezone.now())
        taken = User.objects.exclude(email="asha@example.com").get().email
        response = self.client.post(
            self.CHANGE, {"email": "asha@example.com", "password": PASSWORD, "new_email": taken}, format="json"
        )
        self.assertEqual((response.status_code, response.json()["code"]), (409, "email_taken"))

    @override_settings(LOGIN_MAX_FAILURES=2)
    def test_correction_attempts_count_toward_the_sign_in_lock(self):
        self.register()
        for _ in range(2):
            self.client.post(
                self.CHANGE, {"email": "asha@example.com", "password": "wrong", "new_email": "x@example.com"}, format="json"
            )
        self.assertEqual(self.login().status_code, 429)

    # --- existing data and configuration ---------------------------------------------------------

    def test_existing_accounts_and_profiles_are_kept_and_unverified_ones_must_verify(self):
        profile = make_profile(user=make_user(email_verified_at=None), display_name="Legacy Member")
        user = profile.user
        response = self.client.post(self.RESEND, {"email": user.email}, format="json")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(self.verify(token_from(mail.outbox[-1])).status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.display_name, "Legacy Member")
        self.assertEqual(self.login(email=user.email).status_code, 200)

    def test_settings_never_hardcode_smtp_credentials(self):
        settings_dir = Path(settings.BASE_DIR) / "config" / "settings"
        for path in settings_dir.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            for line in source.splitlines():
                if "EMAIL_HOST_PASSWORD" in line and "=" in line and not line.lstrip().startswith("#"):
                    with self.subTest(file=path.name):
                        self.assertRegex(line, r'EMAIL_HOST_PASSWORD = env\.str\("EMAIL_HOST_PASSWORD", default=""\)')

    @override_settings(EMAIL_PROVIDER="smtp", EMAIL_HOST_PASSWORD="app-password-secret")
    def test_smtp_failures_never_log_the_password(self):
        from apps.notifications.mail import EmailError, send_email

        with mock.patch("django.core.mail.send_mail", side_effect=OSError("auth failed app-password-secret")), mock.patch(
            "apps.notifications.mail.send_mail", side_effect=OSError("auth failed app-password-secret")
        ):
            with self.assertRaises(EmailError) as raised:
                send_email("a@example.com", "Subject", "Body")
        self.assertNotIn("app-password-secret", str(raised.exception))


class RegistrationValidationAndDeliveryTests(TestCase):
    URL = "/api/v1/auth/register/"

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def valid(self, **overrides):
        return {
            "email": "lekha@example.com", "password": PASSWORD, "phone_number": "+919812345600",
            "accept_terms": True, "created_for": "self", "display_name": "Lekha Das", "gender": "female",
            "date_of_birth": f"{timezone.now().year - 26}-01-01", **overrides,
        }

    def test_every_required_field_is_reported(self):
        response = self.client.post(self.URL, {}, format="json")
        self.assertEqual(response.status_code, 400)
        for field in ("email", "password", "phone_number", "accept_terms", "created_for", "display_name", "gender",
                      "date_of_birth"):
            self.assertIn(field, response.json())
        self.assertFalse(User.objects.exists())

    def test_invalid_email_and_mobile_are_rejected(self):
        for overrides, field in (({"email": "not-an-email"}, "email"), ({"phone_number": "12345"}, "phone_number")):
            with self.subTest(field=field):
                response = self.client.post(self.URL, self.valid(**overrides), format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        self.assertFalse(User.objects.exists())

    def test_email_is_normalised_and_password_hashed(self):
        self.client.post(self.URL, self.valid(email="  Lekha@EXAMPLE.com "), format="json")
        user = User.objects.get()
        self.assertEqual(user.email, "lekha@example.com")
        self.assertNotIn(PASSWORD, user.password)
        self.assertTrue(user.password.startswith(("pbkdf2_", "argon2", "bcrypt", "md5")))
        self.assertTrue(user.check_password(PASSWORD))

    def test_response_says_how_the_email_was_handled(self):
        body = self.client.post(self.URL, self.valid(), format="json").json()
        self.assertEqual(body["delivery"], "locmem")
        with override_settings(EMAIL_PROVIDER="console", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            body = self.client.post(
                self.URL, self.valid(email="second@example.com", phone_number="+919812345601"), format="json"
            ).json()
        self.assertEqual(body["delivery"], "console")

    def test_profile_and_account_are_created_together_or_not_at_all(self):
        from apps.profiles.models import Profile

        with mock.patch("apps.profiles.services.create_profile", side_effect=RuntimeError("boom at line 42")):
            with self.assertLogs("apps.core.exceptions", "ERROR"):
                response = self.client.post(self.URL, self.valid(), format="json")
        # A generic error: no traceback, SQL or internal message reaches the visitor.
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "An unexpected error occurred. Please try again later."})
        self.assertFalse(User.objects.exists())
        self.assertFalse(Profile.objects.exists())


class EmailFailureDescriptionTests(TestCase):
    @override_settings(EMAIL_PROVIDER="smtp", EMAIL_HOST="smtp.gmail.com", EMAIL_PORT=587)
    def test_failures_name_the_setting_to_check_without_the_server_reply(self):
        import smtplib

        from apps.notifications.mail import describe_failure

        auth = describe_failure(smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted for me@x"))
        self.assertIn("EMAIL_HOST_PASSWORD", auth)
        self.assertNotIn("me@x", auth)
        self.assertIn("smtp.gmail.com:587", describe_failure(TimeoutError()))
        self.assertIn("DEFAULT_FROM_EMAIL", describe_failure(smtplib.SMTPSenderRefused(553, b"no", "a@b")))


class SendTestEmailCommandTests(TestCase):
    def run_command(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("send_test_email", *args, stdout=out)
        return out.getvalue()

    def test_sends_one_message_through_the_configured_backend(self):
        output = self.run_command("check@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["check@example.com"])
        self.assertIn("Accepted", output)

    @override_settings(EMAIL_PROVIDER="smtp", EMAIL_HOST="", EMAIL_HOST_USER="", EMAIL_HOST_PASSWORD="")
    def test_reports_missing_settings_without_values(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as raised:
            self.run_command("check@example.com")
        message = str(raised.exception)
        self.assertIn("EMAIL_HOST is empty", message)
        self.assertIn("EMAIL_HOST_PASSWORD is empty", message)
        self.assertEqual(mail.outbox, [])

    @override_settings(EMAIL_PROVIDER="smtp", EMAIL_HOST="smtp.gmail.com", EMAIL_HOST_USER="me@gmail.com",
                       EMAIL_HOST_PASSWORD="app-password-secret")
    def test_smtp_rejection_is_explained_and_the_password_never_printed(self):
        import smtplib

        from django.core.management.base import CommandError

        error = smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
        with mock.patch("apps.notifications.mail.send_mail", side_effect=error):
            with self.assertRaises(CommandError) as raised:
                output = self.run_command("check@example.com")
        message = str(raised.exception)
        self.assertIn("App Password", message)
        self.assertNotIn("app-password-secret", message)
        self.assertNotIn("app-password-secret", locals().get("output", ""))


class RegistrationAtTheEmailCapTests(TestCase):
    @override_settings(EMAIL_VERIFICATION_MAX_PER_HOUR=2)
    def test_registering_an_address_that_hit_the_hourly_cap_is_not_a_server_error(self):
        cache.clear()
        client = APIClient()
        # Earlier sends to this address (e.g. an account that was since deleted) used up the hour.
        for _ in range(2):
            client.post("/api/v1/auth/email/resend/", {"email": "capped@example.com"}, format="json")
        response = client.post("/api/v1/auth/register/", {
            "email": "capped@example.com", "password": PASSWORD, "phone_number": "+919812345611",
            "accept_terms": True, "created_for": "self", "display_name": "Capped Member", "gender": "female",
            "date_of_birth": f"{timezone.now().year - 26}-01-01",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIs(body["email_sent"], False)
        self.assertEqual(body["not_sent_reason"], "rate_limited")
        self.assertIn("already received several emails", body["detail"])
        self.assertTrue(User.objects.filter(email="capped@example.com", email_verified_at=None).exists())
        self.assertEqual(mail.outbox, [])


class VerificationSignInTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = make_user(email_verified_at=None)
        from .email_verification import send_verification_email

        send_verification_email(self.user)
        self.token = token_from(mail.outbox[-1])

    def verify(self, token=None):
        return self.client.post("/api/v1/auth/email/verify/", {"token": token or self.token}, format="json")

    def test_expired_invalid_and_superseded_links_give_no_session(self):
        from .email_verification import send_verification_email

        with override_settings(EMAIL_VERIFICATION_TIMEOUT=1), mock.patch(
            "django.core.signing.time.time", return_value=time.time() + 5
        ):
            self.assertNotIn("access", self.verify().json())
        self.assertNotIn("access", self.verify("garbage").json())
        old = self.token
        send_verification_email(self.user)
        self.assertNotIn("access", self.verify(old).json())
        self.user.refresh_from_db()
        self.assertIsNone(self.user.email_verified_at)

    def test_suspended_account_is_verified_but_not_signed_in(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        response = self.verify()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access", response.json())

    def test_session_from_verification_refreshes_like_a_normal_one(self):
        tokens = self.verify().json()
        refreshed = self.client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(refreshed.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)
