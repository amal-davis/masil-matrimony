"""
SMS one-time-code login for members.

Abuse controls, all enforced here on the server:
- per number: a resend cooldown and an hourly cap on codes (stored in the
  database, so they hold across API processes); the views add per-IP throttles;
- per code: short expiry, a limited number of wrong guesses, single use, and
  any earlier code for the number is invalidated when a new one is issued.

Requests for numbers without an eligible account get the same response as real
ones (a challenge is recorded but no SMS is sent and it can never be verified),
so the endpoint does not reveal which numbers are registered.
"""
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from apps.notifications.sms import SMSError, SMSNotConfigured, send_otp_sms, sms_configured

from .models import PhoneOTPChallenge, User
from .roles import Role

logger = logging.getLogger(__name__)

Purpose = PhoneOTPChallenge.Purpose


class OTPError(Exception):
    code = "otp_error"
    message = "This code can't be used."

    def __init__(self, message=None, **extra):
        self.message = message or self.message
        self.extra = extra
        super().__init__(self.message)


class OTPUnavailable(OTPError):
    code = "otp_unavailable"
    message = "Login by SMS is not available right now. Please try again later."


class OTPDeliveryFailed(OTPError):
    code = "otp_delivery_failed"
    message = "We couldn't send the code right now. Please try again in a few minutes."


class OTPRateLimited(OTPError):
    code = "otp_rate_limited"
    message = "Please wait before requesting another code."


class OTPIncorrect(OTPError):
    code = "otp_incorrect"
    message = "That code is incorrect."


class OTPExpired(OTPError):
    code = "otp_expired"
    message = "This code has expired. Please request a new one."


class OTPAlreadyUsed(OTPError):
    code = "otp_used"
    message = "This code has already been used. Please request a new one."


class OTPAttemptsExceeded(OTPError):
    code = "otp_attempts_exceeded"
    message = "Too many incorrect attempts. Please request a new code."


class OTPInvalid(OTPError):
    code = "otp_invalid"
    message = "This code is no longer valid. Please request a new one."


@dataclass(frozen=True)
class IssuedChallenge:
    challenge_id: str
    code_length: int
    expires_in: int
    resend_after: int


def _hash_code(challenge: PhoneOTPChallenge, code: str) -> str:
    # Keyed with SECRET_KEY, so a leaked table can't be brute-forced offline.
    value = f"{challenge.public_id}:{challenge.purpose}:{challenge.phone_number}:{code}"
    return salted_hmac("apps.accounts.otp", value, algorithm="sha256").hexdigest()


def _generate_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(settings.OTP_CODE_LENGTH))


def _login_user_for(phone_number: str):
    # Phone login is for members; staff sign in with email and password.
    return User.objects.filter(phone_number=phone_number, is_active=True, role=Role.MEMBER).first()


def request_login_code(phone_number: str) -> IssuedChallenge:
    """Issue a login code for an E.164 number and send it by SMS if it belongs to a member."""
    if not sms_configured():
        raise OTPUnavailable()

    now = timezone.now()
    cooldown = settings.OTP_RESEND_COOLDOWN_SECONDS
    ttl = settings.OTP_TTL_SECONDS

    with transaction.atomic():
        created = list(
            PhoneOTPChallenge.objects.filter(
                phone_number=phone_number,
                purpose=Purpose.LOGIN,
                created_at__gte=now - timedelta(hours=1),
            )
            .order_by("created_at")
            .values_list("created_at", flat=True)
        )
        if created:
            waited = (now - created[-1]).total_seconds()
            if waited < cooldown:
                raise OTPRateLimited(retry_after=max(1, int(cooldown - waited)))
        if len(created) >= settings.OTP_MAX_REQUESTS_PER_HOUR:
            retry_after = int((created[0] + timedelta(hours=1) - now).total_seconds()) + 1
            raise OTPRateLimited(
                "You've requested several codes. Please try again later.", retry_after=retry_after
            )

        # Only the newest code for a number can be used.
        PhoneOTPChallenge.objects.filter(
            phone_number=phone_number, purpose=Purpose.LOGIN, used_at=None, invalidated_at=None
        ).update(invalidated_at=now)

        user = _login_user_for(phone_number)
        code = _generate_code()
        challenge = PhoneOTPChallenge(
            purpose=Purpose.LOGIN,
            phone_number=phone_number,
            user=user,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl),
        )
        # Unknown numbers get the hash of a code nobody ever sees.
        challenge.code_hash = _hash_code(challenge, code)
        challenge.save()

    if user is not None:
        # Sent after the commit so the transaction isn't held open during the HTTP call.
        try:
            send_otp_sms(phone_number, code)
        except SMSError as exc:
            # Remove it so a failed send doesn't count towards the cooldown or hourly cap.
            challenge.delete()
            logger.error("OTP SMS not sent for challenge %s: %s", challenge.public_id, exc)
            if isinstance(exc, SMSNotConfigured):
                raise OTPUnavailable() from exc
            raise OTPDeliveryFailed() from exc

    return IssuedChallenge(
        challenge_id=str(challenge.public_id),
        code_length=settings.OTP_CODE_LENGTH,
        expires_in=ttl,
        resend_after=cooldown,
    )


def verify_login_code(challenge_id, code: str) -> User:
    """Return the member a correct code belongs to, consuming the challenge. Raises OTPError otherwise."""
    now = timezone.now()
    max_attempts = settings.OTP_MAX_VERIFY_ATTEMPTS
    error = None
    user = None

    # Errors are raised after the block so failed-attempt counts are committed, not rolled back.
    with transaction.atomic():
        challenge = (
            PhoneOTPChallenge.objects.select_for_update()
            .select_related("user")
            .filter(public_id=challenge_id, purpose=Purpose.LOGIN)
            .first()
        )

        if challenge is None:
            error = OTPInvalid()
        elif challenge.used_at is not None:
            error = OTPAlreadyUsed()
        elif challenge.failed_attempts >= max_attempts:
            error = OTPAttemptsExceeded()
        elif challenge.invalidated_at is not None:
            error = OTPInvalid()
        elif challenge.expires_at <= now:
            error = OTPExpired()
        elif challenge.user is None or not constant_time_compare(
            _hash_code(challenge, code), challenge.code_hash
        ):
            challenge.failed_attempts += 1
            remaining = max_attempts - challenge.failed_attempts
            if remaining <= 0:
                challenge.invalidated_at = now
                error = OTPAttemptsExceeded()
            else:
                error = OTPIncorrect(attempts_remaining=remaining)
            challenge.save(update_fields=["failed_attempts", "invalidated_at"])
        else:
            challenge.used_at = now
            challenge.save(update_fields=["used_at"])
            user = challenge.user
            # The account may have changed since the code was sent.
            if not (
                user.is_active
                and user.role == Role.MEMBER
                and user.phone_number == challenge.phone_number
            ):
                error = OTPInvalid()
            elif user.phone_verified_at is None:
                # Receiving the code proves the member controls this number.
                user.phone_verified_at = now
                user.save(update_fields=["phone_verified_at"])

    if error is not None:
        raise error
    return user


def purge_expired_challenges(older_than=timedelta(days=1)) -> int:
    """Delete challenges that expired more than `older_than` ago. Returns the number deleted."""
    deleted, _ = PhoneOTPChallenge.objects.filter(
        expires_at__lt=timezone.now() - older_than
    ).delete()
    return deleted
