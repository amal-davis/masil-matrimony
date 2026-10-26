import uuid
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications import sms
from apps.profiles.models import Profile
from apps.profiles.test_utils import make_profile, make_user

from .forms import UserCreationForm
from .models import OTPNumberLock, PhoneOTPChallenge
from .otp import purge_expired_challenges
from .permissions import IsContentManager, IsTelecaller, IsVerificationStaff
from .phone import normalize_mobile_number
from .roles import Role
from .views import OTPRequestView, OTPVerifyView, RegisterView

User = get_user_model()
PASSWORD = "Str0ng-test-passphrase"


def wrong(code):
    """A code of the same length that is certainly different."""
    return "".join(str((int(digit) + 1) % 10) for digit in code)


def age_challenges(seconds):
    """Pretend every challenge was issued `seconds` earlier."""
    for challenge in PhoneOTPChallenge.objects.all():
        challenge.created_at -= timedelta(seconds=seconds)
        challenge.expires_at -= timedelta(seconds=seconds)
        challenge.save()


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

    def test_member_email_is_optional(self):
        first = User.objects.create_user(phone_number="+919000000101")
        second = User.objects.create_user(email="", phone_number="+919000000102")
        self.assertIsNone(first.email)
        self.assertIsNone(second.email)
        self.assertFalse(first.has_usable_password())
        self.assertEqual(str(first), "+919000000101")

    def test_staff_need_an_email_address(self):
        with self.assertRaises(ValidationError):
            User.objects.create_user(phone_number="+919000000103", role=Role.ADMIN, password=PASSWORD)
        with self.assertRaises(ValueError):
            User.objects.create_superuser(email="", password=PASSWORD)

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

    def test_email_and_phone_are_unique(self):
        User.objects.create_user(email="dup@example.com", phone_number="+919000000104")
        with self.assertRaises(ValidationError):
            User.objects.create_user(email="DUP@example.com")
        with self.assertRaises(ValidationError):
            User.objects.create_user(phone_number="+919000000104")

    def test_changing_the_number_clears_its_verification(self):
        user = make_user()
        self.assertIsNotNone(user.phone_verified_at)
        user.first_name = "Unchanged number"
        user.save()
        user.refresh_from_db()
        self.assertIsNotNone(user.phone_verified_at)

        user.phone_number = "+919000000105"
        user.save(update_fields=["phone_number"])
        user.refresh_from_db()
        self.assertIsNone(user.phone_verified_at)


class MobileNumberTests(TestCase):
    def test_common_ways_of_writing_a_number_give_one_form(self):
        for typed in ("+919876543210", "+91 98765 43210", "+91-98765-43210", "0091 9876543210", "+91 (987) 654-3210"):
            with self.subTest(typed=typed):
                self.assertEqual(normalize_mobile_number(typed), "+919876543210")

    def test_invalid_and_unsupported_numbers(self):
        for typed in ("9876543210", "+0123456789", "", "+915876543210", "+91987654321", "+447911123456", "abc", None):
            with self.subTest(typed=typed):
                with self.assertRaises(ValidationError):
                    normalize_mobile_number(typed)

    @override_settings(SMS_ALLOWED_COUNTRY_CODES=["91", "971"])
    def test_other_countries_only_when_allowed(self):
        self.assertEqual(normalize_mobile_number("+971 50 123 4567"), "+971501234567")
        with self.assertRaises(ValidationError):
            normalize_mobile_number("+447911123456")


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


class StaffTokenApiTests(TestCase):
    """Email + password tokens remain for staff API clients only."""

    URL = "/api/v1/auth/token/"

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(email="staff@example.com", password=PASSWORD, role=Role.ADMIN)

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get("/api/v1/auth/me/").status_code, 401)

    def test_wrong_password_fails(self):
        response = self.client.post(self.URL, {"email": "staff@example.com", "password": "wrong"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_staff_token_login_me_refresh_and_logout(self):
        tokens = self.client.post(self.URL, {"email": "staff@example.com", "password": PASSWORD}, format="json").json()
        self.assertEqual(set(tokens), {"access", "refresh"})

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        me = self.client.get("/api/v1/auth/me/").json()
        self.assertEqual(me["id"], str(self.staff.public_id))
        self.assertNotIn("password", me)
        self.client.credentials()

        rotated = self.client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(rotated.status_code, 200)
        # The original refresh token was blacklisted on rotation.
        reuse = self.client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(reuse.status_code, 401)
        logout = self.client.post("/api/v1/auth/token/blacklist/", {"refresh": rotated.json()["refresh"]}, format="json")
        self.assertEqual(logout.status_code, 200)

    def test_refresh_for_an_account_that_no_longer_exists_is_401(self):
        user = make_user()
        refresh = str(RefreshToken.for_user(user))
        user.delete()
        response = self.client.post("/api/v1/auth/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_members_cannot_use_a_password_even_one_set_before(self):
        make_user(email="legacy@example.com")  # verified mobile and a password from the old sign-in
        response = self.client.post(self.URL, {"email": "legacy@example.com", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access", response.json())

    def test_password_endpoints_are_gone(self):
        for url in ("/api/v1/auth/login/", "/api/v1/auth/password/reset/", "/api/v1/auth/email/verify/",
                    "/api/v1/auth/email/resend/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {}, format="json").status_code, 404)


class OTPLoginApiTests(TestCase):
    REQUEST_URL = "/api/v1/auth/otp/request/"
    VERIFY_URL = "/api/v1/auth/otp/verify/"
    PHONE = "+919876543210"
    RESPONSE_FIELDS = {"challenge_id", "phone_number", "code_length", "expires_in", "resend_after"}

    def setUp(self):
        sms.outbox.clear()
        self.client = APIClient()
        # A member whose number hasn't been proved yet (e.g. registered before SMS sign-in).
        self.member = User.objects.create_user(email="otp@example.com", phone_number=self.PHONE)

    def request_code(self, phone=PHONE):
        return self.client.post(self.REQUEST_URL, {"phone_number": phone}, format="json")

    def verify(self, challenge_id, code):
        return self.client.post(self.VERIFY_URL, {"challenge_id": challenge_id, "code": code}, format="json")

    def issue(self, phone=PHONE):
        """Request a code; return (challenge_id, code)."""
        response = self.request_code(phone)
        self.assertEqual(response.status_code, 202)
        return response.json()["challenge_id"], sms.outbox[-1][1]

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

    def test_number_is_normalised_before_lookup(self):
        response = self.request_code("+91 98765-43210")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["phone_number"], self.PHONE)
        self.assertEqual(sms.outbox[-1][0], self.PHONE)

    def test_unregistered_number_gets_same_response_without_sms(self):
        response = self.request_code("+919000000001")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(set(response.json()), self.RESPONSE_FIELDS)
        self.assertEqual(sms.outbox, [])

    def test_login_never_creates_an_account(self):
        challenge_id = self.request_code("+919000000001").json()["challenge_id"]
        self.verify(challenge_id, "123456")
        self.assertFalse(User.objects.filter(phone_number="+919000000001").exists())
        self.assertEqual(User.objects.count(), 1)

    def test_staff_and_inactive_accounts_get_no_sms(self):
        User.objects.create_user(
            email="staff@example.com", password=PASSWORD, phone_number="+919000000002", role=Role.ADMIN
        )
        User.objects.create_user(email="off@example.com", phone_number="+919000000003", is_active=False)
        self.assertEqual(self.request_code("+919000000002").status_code, 202)
        self.assertEqual(self.request_code("+919000000003").status_code, 202)
        self.assertEqual(sms.outbox, [])

    def test_invalid_phone_number_is_rejected(self):
        invalid = [
            "9876543210",  # no country code
            "+0123456789",
            "",
            "+91987654321012345",
            "+447911123456",  # valid UK mobile, but only India is enabled
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

        age_challenges(settings.OTP_RESEND_COOLDOWN_SECONDS)
        self.assertEqual(self.request_code().status_code, 202)

    def test_cooldown_applies_to_unregistered_numbers_too(self):
        self.request_code("+919000000001")
        self.assertEqual(self.request_code("+919000000001").status_code, 429)

    @override_settings(OTP_MAX_REQUESTS_PER_HOUR=3)
    def test_hourly_limit_per_number(self):
        for _ in range(3):
            self.issue()
            age_challenges(settings.OTP_RESEND_COOLDOWN_SECONDS)
        response = self.request_code()
        self.assertEqual(response.status_code, 429)
        self.assertIn("several codes", response.json()["detail"])
        self.assertEqual(len(sms.outbox), 3)

        age_challenges(3600)
        self.assertEqual(self.request_code().status_code, 202)

    @override_settings(OTP_MAX_REQUESTS_PER_HOUR=100, OTP_MAX_REQUESTS_PER_DAY=4)
    def test_daily_limit_per_number(self):
        for _ in range(4):
            self.issue()
            age_challenges(3600)
        response = self.request_code()
        self.assertEqual(response.status_code, 429)
        self.assertGreater(response.json()["retry_after"], 3600)
        age_challenges(86400)
        self.assertEqual(self.request_code().status_code, 202)

    def test_new_code_invalidates_previous_code(self):
        old_id, old_code = self.issue()
        age_challenges(settings.OTP_RESEND_COOLDOWN_SECONDS)
        new_id, new_code = self.issue()

        response = self.verify(old_id, old_code)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "otp_invalid")
        self.assertEqual(self.verify(new_id, new_code).status_code, 200)

    def test_requests_for_a_number_take_its_lock(self):
        self.issue()
        # One lock row per number, keyed by an HMAC: no phone number is stored in it.
        lock = OTPNumberLock.objects.get()
        self.assertNotIn("9876543210", lock.key)

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

    def test_logs_never_contain_the_code_or_full_number(self):
        with self.assertLogs("apps.accounts.otp", level="INFO") as logs:
            challenge_id, code = self.issue()
            self.verify(challenge_id, wrong(code))
            self.verify(challenge_id, code)
        output = "\n".join(logs.output)
        self.assertIn("OTP issued", output)
        self.assertIn("reason=otp_incorrect", output)
        self.assertIn("OTP verified", output)
        self.assertNotIn(code, output)
        self.assertNotIn(self.PHONE, output)

    # --- Verifying a code --------------------------------------------------

    def test_successful_verification_issues_working_tokens_and_verifies_the_number(self):
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

        refreshed = self.client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(refreshed.status_code, 200)

        self.member.refresh_from_db()
        self.assertIsNotNone(self.member.phone_verified_at)
        self.assertIsNotNone(self.member.last_login)

    def test_incorrect_code(self):
        challenge_id, code = self.issue()
        response = self.verify(challenge_id, wrong(code))
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["code"], "otp_incorrect")
        self.assertNotIn("access", body)
        self.assertEqual(body["attempts_remaining"], settings.OTP_MAX_VERIFY_ATTEMPTS - 1)
        # A wrong guess doesn't burn the challenge.
        self.assertEqual(self.verify(challenge_id, code).status_code, 200)

    def test_too_many_failed_attempts_invalidates_code(self):
        challenge_id, code = self.issue()
        for _ in range(settings.OTP_MAX_VERIFY_ATTEMPTS - 1):
            self.assertEqual(self.verify(challenge_id, wrong(code)).json()["code"], "otp_incorrect")
        last = self.verify(challenge_id, wrong(code))
        self.assertEqual(last.json()["code"], "otp_attempts_exceeded")

        # Even the right code no longer works.
        response = self.verify(challenge_id, code)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "otp_attempts_exceeded")

    def test_expired_code(self):
        challenge_id, code = self.issue()
        age_challenges(settings.OTP_TTL_SECONDS)
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

    def test_number_changed_after_code_sent(self):
        challenge_id, code = self.issue()
        User.objects.filter(pk=self.member.pk).update(phone_number="+919000000009")
        self.assertEqual(self.verify(challenge_id, code).json()["code"], "otp_invalid")

    def test_code_is_bound_to_its_challenge_and_account(self):
        other = User.objects.create_user(email="other@example.com", phone_number="+919000000004")
        mine_id, mine_code = self.issue()
        _, other_code = self.issue("+919000000004")
        if other_code != mine_code:  # 1-in-a-million chance the digits match
            self.assertEqual(self.verify(mine_id, other_code).json()["code"], "otp_incorrect")
        # A login code can't complete a registration, or vice versa.
        response = self.client.post(
            "/api/v1/auth/register/verify/", {"challenge_id": mine_id, "code": mine_code}, format="json"
        )
        self.assertEqual(response.json()["code"], "otp_invalid")
        tokens = self.verify(mine_id, mine_code).json()
        self.assertNotEqual(RefreshToken(tokens["refresh"])["user_id"], str(other.public_id))
        self.assertEqual(RefreshToken(tokens["refresh"])["user_id"], str(self.member.public_id))

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
        age_challenges(2 * 86400)
        self.request_code("+919000000001")
        self.assertEqual(purge_expired_challenges(), 1)
        self.assertEqual(PhoneOTPChallenge.objects.count(), 1)


class RegistrationApiTests(TestCase):
    URL = "/api/v1/auth/register/"
    RESEND_URL = "/api/v1/auth/register/resend/"
    VERIFY_URL = "/api/v1/auth/register/verify/"
    PHONE = "+919812345600"

    def setUp(self):
        sms.outbox.clear()
        cache.clear()
        self.client = APIClient()

    def valid(self, **overrides):
        return {
            "phone_number": self.PHONE, "email": "lekha@example.com", "accept_terms": True,
            "created_for": "self", "display_name": "Lekha Das", "gender": "female",
            "date_of_birth": f"{timezone.now().year - 26}-01-01", **overrides,
        }

    def start(self, **overrides):
        """Start a registration; return (challenge_id, code)."""
        response = self.client.post(self.URL, self.valid(**overrides), format="json")
        self.assertEqual(response.status_code, 202, response.content)
        return response.json()["challenge_id"], sms.outbox[-1][1]

    def verify(self, challenge_id, code):
        return self.client.post(self.VERIFY_URL, {"challenge_id": challenge_id, "code": code}, format="json")

    def resend(self, challenge_id, **extra):
        return self.client.post(self.RESEND_URL, {"challenge_id": challenge_id, **extra}, format="json")

    # --- Starting ----------------------------------------------------------

    def test_valid_registration_sends_a_code_and_creates_nothing_yet(self):
        response = self.client.post(self.URL, self.valid(phone_number="+91 98123 45600"), format="json")
        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["phone_number"], self.PHONE)
        self.assertEqual(sms.outbox[-1][0], self.PHONE)
        # No account and no tokens until the code is verified.
        self.assertNotIn("access", body)
        self.assertFalse(User.objects.exists())
        self.assertFalse(Profile.objects.exists())
        challenge = PhoneOTPChallenge.objects.get()
        self.assertEqual(challenge.purpose, PhoneOTPChallenge.Purpose.REGISTER)
        self.assertEqual(challenge.registration["display_name"], "Lekha Das")

    def test_every_required_field_is_reported(self):
        response = self.client.post(self.URL, {}, format="json")
        self.assertEqual(response.status_code, 400)
        for field in ("phone_number", "accept_terms", "created_for", "display_name", "gender", "date_of_birth"):
            self.assertIn(field, response.json())
        # Email is required (receipts go there); there is no password.
        self.assertIn("email", response.json())
        self.assertNotIn("password", response.json())
        self.assertEqual(sms.outbox, [])

    def test_invalid_data_is_rejected_without_sending_anything(self):
        cases = [
            ({"email": "not-an-email"}, "email"),
            ({"phone_number": "12345"}, "phone_number"),
            ({"phone_number": "+447911123456"}, "phone_number"),
            ({"accept_terms": False}, "accept_terms"),
            ({"gender": "other"}, "gender"),
            ({"display_name": "123"}, "display_name"),
            # Under the minimum age for a bride.
            ({"date_of_birth": f"{timezone.now().year - 16}-01-01"}, "date_of_birth"),
        ]
        for overrides, field in cases:
            with self.subTest(field=field, overrides=overrides):
                response = self.client.post(self.URL, self.valid(**overrides), format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        self.assertEqual(sms.outbox, [])
        self.assertFalse(PhoneOTPChallenge.objects.exists())

    def test_duplicate_mobile_number_is_sent_to_login(self):
        existing = make_profile(make_user(phone_number=self.PHONE, email="first@example.com")).user
        for phone in (self.PHONE, "+91 98123 45600"):
            with self.subTest(phone=phone):
                response = self.client.post(self.URL, self.valid(phone_number=phone, email="other@example.com"), format="json")
                self.assertEqual(response.status_code, 409)
                body = response.json()
                self.assertEqual(body["code"], "phone_registered")
                self.assertIn("log in", body["detail"])
                self.assertIn("phone_number", body)
        self.assertEqual(sms.outbox, [])
        # The existing member's details are untouched.
        existing.refresh_from_db()
        self.assertEqual(existing.email, "first@example.com")
        self.assertEqual(existing.profile.display_name, Profile.objects.get(user=existing).display_name)
        self.assertEqual(User.objects.count(), 1)

    def test_email_used_by_another_account_is_reported(self):
        make_user(email="lekha@example.com")
        response = self.client.post(self.URL, self.valid(email="LEKHA@example.com"), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())

    def test_provider_failure_leaves_nothing_behind(self):
        with mock.patch.dict(sms._PROVIDERS, {"locmem": mock.Mock(side_effect=sms.SMSError("down"))}):
            with self.assertLogs("apps.accounts.otp", level="ERROR"):
                response = self.client.post(self.URL, self.valid(), format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "otp_delivery_failed")
        self.assertFalse(PhoneOTPChallenge.objects.exists())
        self.assertFalse(User.objects.exists())

    @override_settings(SMS_PROVIDER="")
    def test_unavailable_without_an_sms_provider(self):
        response = self.client.post(self.URL, self.valid(), format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "otp_unavailable")
        self.assertFalse(PhoneOTPChallenge.objects.exists())

    # --- Verifying ----------------------------------------------------------

    def test_correct_code_creates_a_verified_account_and_profile_and_signs_in(self):
        challenge_id, code = self.start(phone_number="+91 98123-45600")
        response = self.verify(challenge_id, code)
        self.assertEqual(response.status_code, 201)
        tokens = response.json()
        self.assertEqual(set(tokens), {"access", "refresh"})

        user = User.objects.get()
        self.assertEqual(user.phone_number, self.PHONE)
        self.assertIsNotNone(user.phone_verified_at)
        self.assertEqual(user.email, "lekha@example.com")
        self.assertIsNone(user.email_verified_at)
        self.assertFalse(user.has_usable_password())
        self.assertEqual((user.first_name, user.last_name), ("Lekha", "Das"))
        self.assertEqual(user.role, Role.MEMBER)
        profile = user.profile
        self.assertEqual((profile.display_name, profile.gender, profile.created_for), ("Lekha Das", "female", "self"))

        # The session works on member endpoints straight away.
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.get("/api/v1/dashboard/summary/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/memberships/me/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/me/").json()["id"], str(user.public_id))
        # The details aren't kept on the spent challenge.
        self.assertIsNone(PhoneOTPChallenge.objects.get().registration)

    def test_email_is_required_and_normalised(self):
        for value in ("", None, "not-an-email", "a@b"):
            with self.subTest(email=value):
                response = self.client.post(self.URL, self.valid(email=value), format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("email", response.json())
        body = self.client.post(self.URL, {k: v for k, v in self.valid().items() if k != "email"}, format="json").json()
        self.assertIn("payment receipts", body["email"][0])
        self.assertEqual(sms.outbox, [])

        challenge_id, code = self.start(email="  Lekha.Das@EXAMPLE.com ")
        self.assertEqual(self.verify(challenge_id, code).status_code, 201)
        self.assertEqual(User.objects.get().email, "lekha.das@example.com")

    def test_profile_for_a_relative_keeps_the_account_greeting_generic(self):
        challenge_id, code = self.start(created_for="daughter", display_name="Anu Mohan")
        self.verify(challenge_id, code)
        user = User.objects.get()
        self.assertEqual((user.first_name, user.last_name), ("", ""))
        self.assertEqual(user.profile.display_name, "Anu Mohan")

    def test_incorrect_expired_reused_and_exhausted_codes(self):
        challenge_id, code = self.start()
        response = self.verify(challenge_id, wrong(code))
        self.assertEqual((response.status_code, response.json()["code"]), (400, "otp_incorrect"))
        self.assertFalse(User.objects.exists())

        self.assertEqual(self.verify(challenge_id, code).status_code, 201)
        self.assertEqual(self.verify(challenge_id, code).json()["code"], "otp_used")
        self.assertEqual(User.objects.count(), 1)

        challenge_id, code = self.start(phone_number="+919812345601", email="second@example.com")
        age_challenges(settings.OTP_TTL_SECONDS)
        self.assertEqual(self.verify(challenge_id, code).json()["code"], "otp_expired")

        challenge_id, code = self.start(phone_number="+919812345602", email="third@example.com")
        for _ in range(settings.OTP_MAX_VERIFY_ATTEMPTS):
            self.verify(challenge_id, wrong(code))
        self.assertEqual(self.verify(challenge_id, code).json()["code"], "otp_attempts_exceeded")
        self.assertEqual(User.objects.count(), 1)

    def test_unverified_registration_grants_no_access(self):
        challenge_id, _ = self.start()
        # Nothing to sign in with: no account, so neither login codes nor passwords can reach one.
        self.assertFalse(User.objects.exists())
        self.client.post("/api/v1/auth/otp/request/", {"phone_number": self.PHONE}, format="json")
        self.assertEqual(len(sms.outbox), 1)  # only the registration code was ever sent
        self.assertEqual(self.client.get("/api/v1/dashboard/summary/").status_code, 401)

    def test_number_registered_while_the_code_was_on_its_way(self):
        challenge_id, code = self.start()
        make_user(phone_number=self.PHONE)
        response = self.verify(challenge_id, code)
        self.assertEqual((response.status_code, response.json()["code"]), (409, "phone_registered"))
        self.assertEqual(User.objects.count(), 1)
        # The code is spent all the same.
        self.assertEqual(self.verify(challenge_id, code).json()["code"], "otp_used")

    def test_email_taken_while_the_code_was_on_its_way(self):
        challenge_id, code = self.start()
        make_user(email="lekha@example.com")
        response = self.verify(challenge_id, code)
        self.assertEqual((response.status_code, response.json()["code"]), (409, "email_taken"))
        self.assertFalse(User.objects.filter(phone_number=self.PHONE).exists())

    def test_account_and_profile_are_created_together_or_not_at_all(self):
        challenge_id, code = self.start()
        with mock.patch("apps.profiles.services.create_profile", side_effect=RuntimeError("boom at line 42")):
            with self.assertLogs("apps.core.exceptions", "ERROR"):
                response = self.verify(challenge_id, code)
        # A generic error: no traceback, SQL or internal message reaches the visitor.
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "An unexpected error occurred. Please try again later."})
        self.assertFalse(User.objects.exists())
        self.assertFalse(Profile.objects.exists())

    # --- Resending and correcting the number ---------------------------------

    def test_resend_cooldown_then_new_code_supersedes_the_old_one(self):
        old_id, old_code = self.start()
        response = self.resend(old_id)
        self.assertEqual((response.status_code, response.json()["code"]), (429, "otp_rate_limited"))
        self.assertGreater(int(response["Retry-After"]), 0)

        age_challenges(settings.OTP_RESEND_COOLDOWN_SECONDS)
        response = self.resend(old_id)
        self.assertEqual(response.status_code, 202)
        new_id, new_code = response.json()["challenge_id"], sms.outbox[-1][1]
        self.assertNotEqual(new_id, old_id)
        self.assertEqual(self.verify(old_id, old_code).json()["code"], "otp_invalid")
        self.assertEqual(self.verify(new_id, new_code).status_code, 201)
        self.assertEqual(User.objects.get().profile.display_name, "Lekha Das")

    def test_registration_and_login_share_the_per_number_limits(self):
        self.start()
        response = self.client.post("/api/v1/auth/otp/request/", {"phone_number": self.PHONE}, format="json")
        self.assertEqual(response.status_code, 429)

    def test_change_number_before_verifying(self):
        old_id, old_code = self.start()
        response = self.resend(old_id, phone_number="+91 98123 45699")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["phone_number"], "+919812345699")
        self.assertEqual(sms.outbox[-1][0], "+919812345699")
        new_id, new_code = response.json()["challenge_id"], sms.outbox[-1][1]

        self.assertEqual(self.verify(old_id, old_code).json()["code"], "otp_invalid")
        self.assertEqual(self.verify(new_id, new_code).status_code, 201)
        self.assertEqual(User.objects.get().phone_number, "+919812345699")

    def test_change_to_a_registered_number_is_refused(self):
        make_user(phone_number="+919812345699")
        old_id, _ = self.start()
        response = self.resend(old_id, phone_number="+919812345699")
        self.assertEqual((response.status_code, response.json()["code"]), (409, "phone_registered"))

    def test_resend_for_a_completed_unknown_or_old_registration(self):
        challenge_id, code = self.start()
        self.verify(challenge_id, code)
        self.assertEqual(self.resend(challenge_id).status_code, 410)
        self.assertEqual(self.resend(str(uuid.uuid4())).status_code, 410)

        challenge_id, _ = self.start(phone_number="+919812345601", email="second@example.com")
        age_challenges(settings.OTP_REGISTRATION_WINDOW_SECONDS + 1)
        response = self.resend(challenge_id)
        self.assertEqual((response.status_code, response.json()["code"]), (410, "registration_expired"))

    def test_login_challenge_cannot_be_resent_as_a_registration(self):
        make_user(phone_number="+919000000050")
        login_id = self.client.post(
            "/api/v1/auth/otp/request/", {"phone_number": "+919000000050"}, format="json"
        ).json()["challenge_id"]
        self.assertEqual(self.resend(login_id).status_code, 410)

    def test_purge_deletes_details_of_registrations_never_verified(self):
        self.start()
        age_challenges(2 * 86400)
        OTPNumberLock.objects.update(created_at=timezone.now() - timedelta(days=2))
        purge_expired_challenges()
        self.assertFalse(PhoneOTPChallenge.objects.exists())
        self.assertFalse(OTPNumberLock.objects.exists())

    def test_endpoint_is_throttled_per_ip(self):
        self.addCleanup(cache.clear)
        with (
            mock.patch.object(RegisterView, "throttle_classes", [ScopedRateThrottle]),
            mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"register": "2/hour"}),
        ):
            statuses = [
                self.client.post(self.URL, self.valid(phone_number=f"+91981234570{i}", email=f"m{i}@example.com"), format="json").status_code
                for i in range(3)
            ]
        self.assertEqual(statuses, [202, 202, 429])


class PhoneVerificationGateTests(TestCase):
    """Legacy accounts and the rule that members prove their mobile number before using the site."""

    def setUp(self):
        sms.outbox.clear()
        self.client = APIClient()

    def tokens_for(self, user):
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token), str(refresh)

    def test_member_without_a_verified_number_cannot_use_member_apis(self):
        member = make_profile(make_user(phone_verified_at=None)).user
        access, refresh = self.tokens_for(member)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.get("/api/v1/dashboard/summary/")
        self.assertEqual((response.status_code, response.json()["code"]), (403, "phone_not_verified"))
        self.client.credentials()
        # And an older session stops at its next refresh.
        self.assertEqual(
            self.client.post("/api/v1/auth/token/refresh/", {"refresh": refresh}, format="json").status_code, 401
        )

    def test_legacy_member_signs_in_by_sms_which_verifies_the_number(self):
        # Registered under the email flow: email verified, password set, number never proved.
        member = make_profile(
            make_user(email="old@example.com", phone_number="+919000000060", phone_verified_at=None,
                      email_verified_at=timezone.now())
        ).user
        response = self.client.post("/api/v1/auth/otp/request/", {"phone_number": "+919000000060"}, format="json")
        challenge_id, code = response.json()["challenge_id"], sms.outbox[-1][1]
        tokens = self.client.post(
            "/api/v1/auth/otp/verify/", {"challenge_id": challenge_id, "code": code}, format="json"
        ).json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.get("/api/v1/dashboard/summary/").status_code, 200)
        member.refresh_from_db()
        self.assertIsNotNone(member.phone_verified_at)
        # Their data is untouched.
        self.assertEqual(member.email, "old@example.com")
        self.assertTrue(member.check_password(PASSWORD))
        self.assertIsNotNone(member.email_verified_at)

    def test_unverified_email_no_longer_blocks_anything(self):
        member = make_profile(make_user(email_verified_at=None)).user
        access, _ = self.tokens_for(member)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get("/api/v1/dashboard/summary/").status_code, 200)

    def test_a_verified_email_does_not_verify_the_number(self):
        member = make_user(phone_verified_at=None, email_verified_at=timezone.now())
        member.refresh_from_db()
        self.assertIsNone(member.phone_verified_at)

    def test_suspension_still_blocks_everything(self):
        member = make_profile(make_user()).user
        access, refresh = self.tokens_for(member)
        User.objects.filter(pk=member.pk).update(is_active=False)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(self.client.get("/api/v1/dashboard/summary/").status_code, 401)
        self.client.credentials()
        self.assertEqual(
            self.client.post("/api/v1/auth/token/refresh/", {"refresh": refresh}, format="json").status_code, 401
        )

    def test_staff_accounts_are_not_affected(self):
        staff = User.objects.create_user(email="admin@example.com", password=PASSWORD, role=Role.ADMIN)
        response = self.client.post("/api/v1/auth/token/", {"email": staff.email, "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_member_created_in_the_admin_signs_in_by_sms(self):
        form = UserCreationForm(
            data={"email": "", "phone_number": "+919000000070", "role": Role.MEMBER, "usable_password": "false"}
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertIsNone(user.email)
        self.assertIsNone(user.phone_verified_at)
        response = self.client.post("/api/v1/auth/otp/request/", {"phone_number": "+919000000070"}, format="json")
        code = sms.outbox[-1][1]
        verified = self.client.post(
            "/api/v1/auth/otp/verify/", {"challenge_id": response.json()["challenge_id"], "code": code}, format="json"
        )
        self.assertEqual(verified.status_code, 200)

    def test_staff_created_in_the_admin_needs_an_email(self):
        form = UserCreationForm(
            data={"email": "", "phone_number": "", "role": Role.ADMIN, "password1": PASSWORD, "password2": PASSWORD}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_report_command_counts_accounts_needing_help(self):
        make_user()
        make_user(phone_verified_at=None)
        User.objects.create_user(email="nophone@example.com")
        out = StringIO()
        call_command("mobile_login_report", "--list", stdout=out)
        output = out.getvalue()
        self.assertIn("mobile number verified:            1", output)
        self.assertIn("number on file, not yet verified:  1", output)
        self.assertIn("no mobile number:                  1", output)
        self.assertNotIn("nophone@example.com", output)


class MailSettingsTests(TestCase):
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

