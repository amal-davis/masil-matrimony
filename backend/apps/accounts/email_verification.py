"""
Mandatory email verification for member accounts.

A member registers, gets a verification link by email, and can sign in only
after opening it. Until then every way in is refused on the server: password
and SMS-code sign-in, token refresh (so an older session can't continue) and
every member API (apps.accounts.permissions.IsMember). `is_active` is not
involved: it stays the administrator's suspension switch.

The link carries a token made with django.core.signing, salted for this
purpose and signed with SECRET_KEY. It names the account by its public id and
binds it to
- the email address (a link stops working if the address changes), and
- `email_verification_sent_at`, which every new link updates, so only the
  newest link works,
and it expires after EMAIL_VERIFICATION_TIMEOUT. Once the account is verified
the link is spent: opening it again verifies nothing.

The link puts the token in the URL fragment (#token=…), which browsers never
send to a server, so it stays out of access logs and Referer headers.

The verification that actually verifies the account also signs the member in
(VerifyEmailView returns the usual token pair), so they go straight to the
dashboard. That gives the link no more power than the address already has:
whoever controls the inbox can sign in through password reset anyway. A spent,
superseded or expired link signs nobody in.

Sending is capped per address (EMAIL_VERIFICATION_MAX_PER_HOUR), counted in
AuthAttempt so the cap holds across API processes; the views add per-IP throttles.
"""
import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.core import signing
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from apps.notifications.mail import EmailError, email_configured, send_email

from .models import AuthAttempt, User
from .password_auth import (
    SITE_NAME,
    EmailNotVerified,  # noqa: F401  (re-exported for views)
    InvalidCredentials,
    LoginRateLimited,
    PasswordAuthError,
    _attempt_key,
    _check_limit,
    _duration,
    _greeting,
    normalize_email,
)
from .roles import Role

logger = logging.getLogger(__name__)

SALT = "apps.accounts.email_verification"
Kind = AuthAttempt.Kind


class EmailVerificationError(PasswordAuthError):
    code = "email_verification_error"


class VerificationUnavailable(EmailVerificationError):
    code = "email_unavailable"
    message = "We can't send emails right now, so new accounts can't be verified. Please try again later or contact us."


class VerificationRateLimited(EmailVerificationError):
    code = "verification_rate_limited"
    message = "We've sent several verification emails to this address. Please check your inbox and spam folder, or try again later."


class VerificationDeliveryFailed(EmailVerificationError):
    code = "verification_email_failed"
    message = "We couldn't send the verification email just now. Please try again in a few minutes."


class LinkExpired(EmailVerificationError):
    code = "verification_link_expired"
    message = "This verification link has expired. Please request a new one."


class LinkInvalid(EmailVerificationError):
    code = "verification_link_invalid"
    message = "This verification link is invalid or has been replaced by a newer one. Please use the latest link we sent, or request a new one."


class AlreadyVerified(EmailVerificationError):
    code = "email_already_verified"
    message = "This email address has already been verified. You can sign in."


class EmailChangeNotAllowed(EmailVerificationError):
    code = "email_change_not_allowed"
    message = "The email address can only be changed here before it has been verified. Please sign in and contact us instead."


class EmailTaken(EmailVerificationError):
    code = "email_taken"
    message = "Another account already uses this email address."


def requires_verification(user) -> bool:
    """True for member accounts whose email address hasn't been verified. Staff use the admin site instead."""
    return getattr(user, "role", None) == Role.MEMBER and user.email_verified_at is None


def user_authentication_rule(user) -> bool:
    """SIMPLE_JWT["USER_AUTHENTICATION_RULE"]: active, and verified if a member. Applies at sign-in and refresh."""
    return user is not None and user.is_active and not requires_verification(user)


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------


def _email_binding(user: User) -> str:
    return salted_hmac(SALT, user.email, algorithm="sha256").hexdigest()[:24]


def _sent_marker(user: User) -> str:
    sent = user.email_verification_sent_at
    return str(int(sent.timestamp() * 1_000_000)) if sent else ""


def make_token(user: User) -> str:
    payload = {"u": str(user.public_id), "e": _email_binding(user), "n": _sent_marker(user)}
    return signing.dumps(payload, salt=SALT, compress=False)


def verification_link(user: User) -> str:
    return f"{settings.FRONTEND_URL}/verify-email#token={make_token(user)}"


def verify_token(token: str) -> User:
    """
    Mark the account a link belongs to as verified. Raises LinkExpired,
    LinkInvalid (tampered, superseded or for a changed address) or AlreadyVerified.
    """
    try:
        payload = signing.loads(token, salt=SALT, max_age=settings.EMAIL_VERIFICATION_TIMEOUT)
    except signing.SignatureExpired:
        raise LinkExpired() from None
    except signing.BadSignature:
        raise LinkInvalid() from None
    if not isinstance(payload, dict) or not all(isinstance(payload.get(k), str) for k in ("u", "e", "n")):
        raise LinkInvalid()

    with transaction.atomic():
        user = User.objects.select_for_update().filter(public_id=payload["u"], role=Role.MEMBER).first()
        if user is None or not constant_time_compare(payload["e"], _email_binding(user)):
            raise LinkInvalid()
        if user.email_verified_at is not None:
            # A spent link: it verifies nothing more and signs nobody in.
            raise AlreadyVerified()
        if not constant_time_compare(payload["n"], _sent_marker(user)):
            raise LinkInvalid()
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return user


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------


def _support_contact() -> dict:
    """Only the verified business contacts in settings; never an invented address."""
    return {
        "support_email": settings.SUPPORT_EMAIL,
        "contact_url": f"{settings.FRONTEND_URL}/contact",
    }


def _count_send(email: str) -> None:
    key = _attempt_key(email)
    _check_limit(
        key,
        Kind.VERIFICATION_EMAIL,
        settings.EMAIL_VERIFICATION_MAX_PER_HOUR,
        timedelta(hours=1),
        VerificationRateLimited,
    )
    AuthAttempt.objects.create(kind=Kind.VERIFICATION_EMAIL, key=key)


def _deliver(to: str, subject: str, template: str, context: dict) -> None:
    context = {"site_name": SITE_NAME, "site_url": settings.FRONTEND_URL, **_support_contact(), **context}
    text = render_to_string(f"emails/{template}.txt", context)
    html = render_to_string(f"emails/{template}.html", context)
    send_email(to, subject, text, html=html)


def send_verification_email(user: User) -> None:
    """
    Issue a new link (superseding earlier ones) and email it. Counts toward the
    per-address cap. Raises VerificationRateLimited or VerificationDeliveryFailed.
    """
    _count_send(user.email)
    previous = user.email_verification_sent_at
    # The new link is bound to this marker. It is stored only once the email is accepted,
    # so a failed send leaves the member's previous link working.
    now = timezone.now()
    # Strictly later than the previous marker even when the clock hasn't moved (Windows' clock
    # can return the same time for two quick sends), so the earlier link always stops working.
    if previous is not None and now <= previous:
        now = previous + timedelta(microseconds=1)
    user.email_verification_sent_at = now
    try:
        _deliver(
            user.email,
            f"Verify your email address for {SITE_NAME}",
            "verify_email",
            {
                "greeting": _greeting(user),
                "verify_url": verification_link(user),
                "expires_in": _duration(settings.EMAIL_VERIFICATION_TIMEOUT),
            },
        )
    except EmailError as exc:
        user.email_verification_sent_at = previous
        # The link is never logged; the account is identified by its public id only.
        logger.error("Verification email not sent to user %s: %s", user.public_id, exc)
        raise VerificationDeliveryFailed() from exc
    User.objects.filter(pk=user.pk).update(email_verification_sent_at=user.email_verification_sent_at)


def _send_already_registered_notice(user: User) -> None:
    """Someone tried to register an address that already has a verified account: tell its owner, nobody else."""
    try:
        _count_send(user.email)
    except VerificationRateLimited:
        return
    try:
        _deliver(
            user.email,
            f"You already have a {SITE_NAME} account",
            "already_registered",
            {
                "greeting": _greeting(user),
                "login_url": f"{settings.FRONTEND_URL}/login",
                "reset_url": f"{settings.FRONTEND_URL}/forgot-password",
            },
        )
    except EmailError as exc:
        logger.error("Already-registered notice not sent to user %s: %s", user.public_id, exc)


# --------------------------------------------------------------------------
# Registration, resending and correcting the address
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RegistrationOutcome:
    email: str
    # False when no email went out (delivery failed, or the hourly cap was reached); the account still exists.
    email_sent: bool
    # Why nothing was sent: "" (it was sent), "failed" or "rate_limited".
    reason: str = ""


def ensure_email_available() -> None:
    if not email_configured():
        raise VerificationUnavailable()


def complete_registration(user: User) -> RegistrationOutcome:
    """Send the first verification link to a newly created account."""
    try:
        send_verification_email(user)
    except VerificationDeliveryFailed:
        return RegistrationOutcome(user.email, email_sent=False, reason="failed")
    except VerificationRateLimited:
        # The address already got several emails this hour (e.g. an earlier registration). The
        # account is created all the same; the member requests a link once the hour is up.
        return RegistrationOutcome(user.email, email_sent=False, reason="rate_limited")
    return RegistrationOutcome(user.email, email_sent=True)


def handle_duplicate_registration(email: str) -> RegistrationOutcome:
    """
    The address already has an account. The visitor gets the same answer as a new
    registration; the details they typed are discarded (never applied to the
    existing account), and only the address's owner is emailed: a new
    verification link if it is still unverified, otherwise a note that they
    already have an account. Staff or suspended accounts get nothing.
    """
    user = User.objects.filter(email=email).first()
    if user is not None and user.is_active and user.role == Role.MEMBER:
        if user.email_verified_at is None:
            try:
                send_verification_email(user)
            except (VerificationRateLimited, VerificationDeliveryFailed):
                pass
        else:
            _send_already_registered_notice(user)
    return RegistrationOutcome(email, email_sent=True)


def resend_verification(email: str) -> None:
    """
    Send a new link to an unverified member. Returns the same way for unknown,
    verified, staff and suspended addresses (which get nothing). Raises
    VerificationUnavailable, VerificationRateLimited (counted for every address,
    so it reveals nothing) or VerificationDeliveryFailed.
    """
    ensure_email_available()
    email = normalize_email(email)
    user = User.objects.filter(email=email, is_active=True, role=Role.MEMBER, email_verified_at=None).first()
    if user is None:
        _count_send(email)
        return
    send_verification_email(user)


def change_unverified_email(request, current_email: str, password: str, new_email: str) -> User:
    """
    Correct the address of an account that hasn't been verified yet, then send a
    link to the new address. Needs the account's password, so nobody else can
    move an account to their own address; earlier links stop working because
    they are bound to the old address. Raises InvalidCredentials (also counted
    toward the sign-in lock), EmailChangeNotAllowed, EmailTaken,
    VerificationRateLimited or VerificationDeliveryFailed.
    """
    ensure_email_available()
    current_email = normalize_email(current_email)
    new_email = normalize_email(new_email)
    key = _attempt_key(current_email)
    _check_limit(
        key,
        Kind.LOGIN_FAILURE,
        settings.LOGIN_MAX_FAILURES,
        timedelta(seconds=settings.LOGIN_FAILURE_WINDOW_SECONDS),
        LoginRateLimited,
    )
    user = authenticate(request, username=current_email, password=password)
    if user is None or user.role != Role.MEMBER:
        AuthAttempt.objects.create(kind=Kind.LOGIN_FAILURE, key=key)
        raise InvalidCredentials()
    if user.email_verified_at is not None:
        raise EmailChangeNotAllowed()
    if new_email == user.email:
        send_verification_email(user)
        return user
    if User.objects.filter(email=new_email).exists():
        raise EmailTaken()

    try:
        with transaction.atomic():
            user.email = new_email
            user.save(update_fields=["email"])
    except IntegrityError:
        raise EmailTaken() from None
    send_verification_email(user)
    return user
