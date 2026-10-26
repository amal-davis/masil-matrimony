"""
SMS one-time codes: how members sign in, and how a new member proves their
mobile number before their account is created.

Codes are generated here and only their keyed hash is stored, so the SMS
provider (apps.notifications.sms) only delivers them; it never decides whether
a code is right.

Abuse controls, all enforced here on the server:
- per number, across sign-in and registration: a resend cooldown, an hourly and
  a daily cap on codes (stored in the database, so they hold across API
  processes); the views add per-IP throttles;
- requests for the same number are serialised by a row lock (OTPNumberLock),
  so simultaneous requests can't both get past the cooldown;
- per code: short expiry, a limited number of wrong guesses, single use, bound
  to its purpose and number, and any earlier code for the number is
  invalidated when a new one is issued.

Sign-in requests for numbers without an eligible account get the same response
as real ones (a challenge is recorded but no SMS is sent and it can never be
verified), so the sign-in endpoint does not reveal which numbers are registered.

Events are logged with the challenge id and the last four digits of the number;
codes are never logged.
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

from .models import OTPNumberLock, PhoneOTPChallenge, User
from .phone import mask_mobile_number
from .registration import DuplicateAccount, create_member
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
    message = "We can't send SMS codes right now. Please try again later."


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


class RegistrationExpired(OTPError):
    code = "registration_expired"
    message = "Your registration has expired. Please fill in the registration form again."


class PhoneRegistered(OTPError):
    code = "phone_registered"
    message = "An account already uses this mobile number. Please log in instead."


class EmailTaken(OTPError):
    code = "email_taken"
    message = "Another account already uses this email address. Please register again with a different one."


@dataclass(frozen=True)
class IssuedChallenge:
    challenge_id: str
    # E.164, as the code was sent.
    phone_number: str
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


def phone_number_registered(phone_number: str) -> bool:
    return User.objects.filter(phone_number=phone_number).exists()


def _lock_number(phone_number: str) -> None:
    """Hold a row lock for this number until the surrounding transaction ends."""
    key = salted_hmac("apps.accounts.otp.lock", phone_number, algorithm="sha256").hexdigest()
    lock, _ = OTPNumberLock.objects.get_or_create(key=key)
    # Waits here while another request for the same number is issuing a code.
    OTPNumberLock.objects.select_for_update().filter(pk=lock.pk).first()


def _check_limits(phone_number: str, now) -> None:
    """Raise OTPRateLimited (with retry_after) if this number may not get another code yet."""
    created = list(
        PhoneOTPChallenge.objects.filter(phone_number=phone_number, created_at__gte=now - timedelta(days=1))
        .order_by("created_at")
        .values_list("created_at", flat=True)
    )
    if not created:
        return
    waited = (now - created[-1]).total_seconds()
    cooldown = settings.OTP_RESEND_COOLDOWN_SECONDS
    if waited < cooldown:
        raise OTPRateLimited(retry_after=max(1, int(cooldown - waited)))

    for window, limit in (
        (timedelta(hours=1), settings.OTP_MAX_REQUESTS_PER_HOUR),
        (timedelta(days=1), settings.OTP_MAX_REQUESTS_PER_DAY),
    ):
        recent = [at for at in created if at >= now - window]
        if len(recent) >= limit:
            # Allowed again once enough of the oldest codes have left the window.
            frees_at = recent[len(recent) - limit] + window
            raise OTPRateLimited(
                "You've requested several codes for this number. Please try again later.",
                retry_after=max(1, int((frees_at - now).total_seconds()) + 1),
            )


def _issue(phone_number: str, purpose: str, *, user=None, registration=None, deliver: bool) -> IssuedChallenge:
    """Create a challenge for an E.164 number and, if `deliver`, send its code by SMS."""
    if not sms_configured():
        raise OTPUnavailable()

    now = timezone.now()
    ttl = settings.OTP_TTL_SECONDS
    code = _generate_code()
    with transaction.atomic():
        _lock_number(phone_number)
        _check_limits(phone_number, now)

        # Only the newest code for a number can be used, whatever it was for.
        PhoneOTPChallenge.objects.filter(phone_number=phone_number, used_at=None, invalidated_at=None).update(
            invalidated_at=now
        )
        challenge = PhoneOTPChallenge(
            purpose=purpose,
            phone_number=phone_number,
            user=user,
            registration=registration,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl),
        )
        # Unknown numbers at sign-in get the hash of a code nobody ever sees.
        challenge.code_hash = _hash_code(challenge, code)
        challenge.save()

    if deliver:
        # Sent after the commit so the transaction isn't held open during the HTTP call.
        try:
            send_otp_sms(phone_number, code)
        except SMSError as exc:
            # Removed, so a failed send leaves no usable code (and no pending registration)
            # and doesn't count towards the cooldown or the caps.
            challenge.delete()
            logger.error(
                "OTP not sent: purpose=%s challenge=%s number=%s: %s",
                purpose, challenge.public_id, mask_mobile_number(phone_number), exc,
            )
            if isinstance(exc, SMSNotConfigured):
                raise OTPUnavailable() from exc
            raise OTPDeliveryFailed() from exc

    logger.info(
        "OTP issued: purpose=%s challenge=%s number=%s sent=%s",
        purpose, challenge.public_id, mask_mobile_number(phone_number), deliver,
    )
    return IssuedChallenge(
        challenge_id=str(challenge.public_id),
        phone_number=phone_number,
        code_length=settings.OTP_CODE_LENGTH,
        expires_in=ttl,
        resend_after=settings.OTP_RESEND_COOLDOWN_SECONDS,
    )


def _check_code(challenge, code: str, now):
    """
    The error for this attempt, or None if the code is right. Counts a wrong
    guess on the (locked) challenge. Doesn't mark it used.
    """
    max_attempts = settings.OTP_MAX_VERIFY_ATTEMPTS
    if challenge is None:
        return OTPInvalid()
    if challenge.used_at is not None:
        return OTPAlreadyUsed()
    if challenge.failed_attempts >= max_attempts:
        return OTPAttemptsExceeded()
    if challenge.invalidated_at is not None:
        return OTPInvalid()
    if challenge.expires_at <= now:
        return OTPExpired()
    deliverable = challenge.user is not None or challenge.purpose == Purpose.REGISTER
    if deliverable and constant_time_compare(_hash_code(challenge, code), challenge.code_hash):
        return None

    challenge.failed_attempts += 1
    remaining = max_attempts - challenge.failed_attempts
    if remaining <= 0:
        challenge.invalidated_at = now
        error = OTPAttemptsExceeded()
    else:
        error = OTPIncorrect(attempts_remaining=remaining)
    challenge.save(update_fields=["failed_attempts", "invalidated_at"])
    return error


def _locked_challenge(challenge_id, purpose):
    return (
        PhoneOTPChallenge.objects.select_for_update()
        .select_related("user")
        .filter(public_id=challenge_id, purpose=purpose)
        .first()
    )


def _log_verification(purpose, challenge_id, error) -> None:
    if error is None:
        logger.info("OTP verified: purpose=%s challenge=%s", purpose, challenge_id)
    else:
        logger.info("OTP rejected: purpose=%s challenge=%s reason=%s", purpose, challenge_id, error.code)


# --------------------------------------------------------------------------
# Sign-in
# --------------------------------------------------------------------------


def request_login_code(phone_number: str) -> IssuedChallenge:
    """Issue a sign-in code for an E.164 number and send it by SMS if it belongs to a member."""
    user = _login_user_for(phone_number)
    return _issue(phone_number, Purpose.LOGIN, user=user, deliver=user is not None)


def verify_login_code(challenge_id, code: str) -> User:
    """Return the member a correct code belongs to, consuming the challenge. Raises OTPError otherwise."""
    now = timezone.now()
    user = None

    # Errors are raised after the block so failed-attempt counts are committed, not rolled back.
    with transaction.atomic():
        challenge = _locked_challenge(challenge_id, Purpose.LOGIN)
        error = _check_code(challenge, code, now)
        if error is None:
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

    _log_verification(Purpose.LOGIN, challenge_id, error)
    if error is not None:
        raise error
    return user


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


def start_registration(phone_number: str, details: dict) -> IssuedChallenge:
    """
    Send a code to the number being registered. `details` are the validated,
    JSON-serialisable registration details (apps.accounts.registration); no
    account exists until the code is verified.
    """
    if phone_number_registered(phone_number):
        raise PhoneRegistered()
    return _issue(phone_number, Purpose.REGISTER, registration=details, deliver=True)


def resend_registration_code(challenge_id, phone_number: str | None = None) -> IssuedChallenge:
    """
    Send a new code for a registration in progress, optionally to a corrected
    number, without the form being filled in again. Raises RegistrationExpired
    if the registration was completed or is older than OTP_REGISTRATION_WINDOW_SECONDS.
    """
    window = timedelta(seconds=settings.OTP_REGISTRATION_WINDOW_SECONDS)
    previous = PhoneOTPChallenge.objects.filter(
        public_id=challenge_id,
        purpose=Purpose.REGISTER,
        used_at=None,
        created_at__gte=timezone.now() - window,
    ).first()
    if previous is None or not previous.registration:
        raise RegistrationExpired()

    new_number = phone_number or previous.phone_number
    issued = start_registration(new_number, previous.registration)
    if new_number != previous.phone_number:
        # The code sent to the old number must not complete the registration either.
        PhoneOTPChallenge.objects.filter(pk=previous.pk, invalidated_at=None).update(invalidated_at=timezone.now())
    return issued


def complete_registration(challenge_id, code: str) -> User:
    """
    Check the code and create the member's account (mobile number verified)
    and draft profile from the stored details, consuming the challenge.
    Raises OTPError, including PhoneRegistered or EmailTaken if another account
    took the number or address while the code was on its way.
    """
    now = timezone.now()
    user = None

    with transaction.atomic():
        challenge = _locked_challenge(challenge_id, Purpose.REGISTER)
        error = _check_code(challenge, code, now)
        if error is None:
            challenge.used_at = now
            challenge.save(update_fields=["used_at"])
            try:
                # A savepoint, so a duplicate rolls back only the account, not the spent code.
                with transaction.atomic():
                    user = create_member(challenge.phone_number, challenge.registration, phone_verified_at=now)
            except DuplicateAccount as duplicate:
                error = EmailTaken() if duplicate.field == "email" else PhoneRegistered()
            else:
                # The details have done their job; don't keep personal data on a spent challenge.
                challenge.registration = None
                challenge.save(update_fields=["registration"])

    _log_verification(Purpose.REGISTER, challenge_id, error)
    if error is not None:
        raise error
    logger.info("Member registered: user=%s challenge=%s", user.public_id, challenge_id)
    return user


def purge_expired_challenges(older_than=timedelta(days=1)) -> int:
    """
    Delete challenges (with any registration details they hold) that expired
    more than `older_than` ago, and number locks as old. Returns the number of challenges deleted.
    """
    cutoff = timezone.now() - older_than
    deleted, _ = PhoneOTPChallenge.objects.filter(expires_at__lt=cutoff).delete()
    OTPNumberLock.objects.filter(created_at__lt=cutoff).delete()
    return deleted
