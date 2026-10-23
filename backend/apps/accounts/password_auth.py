"""
Email + password sign-in and password reset for members.

Passwords are checked by Django's authentication backend (ModelBackend), so
they are only ever compared as salted hashes, and an unknown email costs the
same hashing work as a wrong password.

Abuse controls, all enforced here on the server:
- per email address: failed logins lock the address for the rest of a window
  (LOGIN_MAX_FAILURES per LOGIN_FAILURE_WINDOW_SECONDS), and reset emails are
  capped per hour (PASSWORD_RESET_MAX_PER_HOUR). Both are stored in the
  database so they hold across API processes; the views add per-IP throttles.
- per reset link: Django's token generator signs the link with the account's
  current password hash and last login time, so a link stops working once it
  is used, once the member signs in, or after PASSWORD_RESET_TIMEOUT.

Unknown addresses get the same responses as registered ones, so neither
endpoint reveals which addresses have accounts.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.notifications.mail import EmailError, email_configured, send_email

from .models import AuthAttempt, User
from .roles import Role

logger = logging.getLogger(__name__)

Kind = AuthAttempt.Kind

SITE_NAME = "Massil Matrimony"


class PasswordAuthError(Exception):
    code = "auth_error"
    message = "Something went wrong. Please try again."

    def __init__(self, message=None, **extra):
        self.message = message or self.message
        self.extra = extra
        super().__init__(self.message)


class InvalidCredentials(PasswordAuthError):
    code = "invalid_credentials"
    message = "The email address or password is incorrect."


class LoginRateLimited(PasswordAuthError):
    code = "login_rate_limited"
    message = "Too many unsuccessful sign-in attempts. Please try again later, or reset your password."


class PasswordResetUnavailable(PasswordAuthError):
    code = "password_reset_unavailable"
    message = "Password reset by email is not available right now. Please contact us for help."


class PasswordResetRateLimited(PasswordAuthError):
    code = "password_reset_rate_limited"
    message = "You've requested several reset links. Please check your inbox, or try again later."


class PasswordResetLinkInvalid(PasswordAuthError):
    code = "reset_link_invalid"
    message = "This password reset link is invalid or has expired. Please request a new one."


def normalize_email(email: str) -> str:
    """The form accounts.User stores: domain and local part lower-cased (see UserManager)."""
    return User.objects.normalize_email(email.strip()).lower()


def _attempt_key(email: str) -> str:
    # Keyed with SECRET_KEY, so the table can't be matched against a list of addresses.
    return salted_hmac("apps.accounts.password_auth", normalize_email(email), algorithm="sha256").hexdigest()


def _check_limit(key: str, kind: str, limit: int, window: timedelta, error: type[PasswordAuthError]) -> None:
    """Raise `error` (with retry_after) if `key` already has `limit` attempts of `kind` within `window`."""
    now = timezone.now()
    recent = list(
        AuthAttempt.objects.filter(key=key, kind=kind, created_at__gte=now - window)
        .order_by("created_at")
        .values_list("created_at", flat=True)
    )
    if len(recent) >= limit:
        # Allowed again once enough of the oldest attempts have left the window.
        frees_at = recent[len(recent) - limit] + window
        raise error(retry_after=max(1, int((frees_at - now).total_seconds()) + 1))


def _member_with_email(email: str):
    return User.objects.filter(email=email, is_active=True, role=Role.MEMBER).first()


def _end_all_sessions(user: User) -> None:
    """Blacklist every refresh token issued to `user`, signing out all their devices."""
    outstanding = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in outstanding], ignore_conflicts=True
    )


def _greeting(user: User) -> str:
    return f"Hello {user.first_name}," if user.first_name else "Hello,"


def _duration(seconds: int) -> str:
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    minutes = max(1, seconds // 60)
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"


# --------------------------------------------------------------------------
# Sign-in
# --------------------------------------------------------------------------


def login_with_password(request, email: str, password: str) -> User:
    """Return the member these credentials belong to. Raises InvalidCredentials or LoginRateLimited."""
    email = normalize_email(email)
    key = _attempt_key(email)
    # Checked before the password, so a locked address can't keep guessing.
    _check_limit(
        key,
        Kind.LOGIN_FAILURE,
        settings.LOGIN_MAX_FAILURES,
        timedelta(seconds=settings.LOGIN_FAILURE_WINDOW_SECONDS),
        LoginRateLimited,
    )

    # ModelBackend: refuses inactive accounts and accounts without a usable password.
    user = authenticate(request, username=email, password=password)
    # The website is for members; staff sign in to the admin site.
    if user is None or user.role != Role.MEMBER:
        AuthAttempt.objects.create(kind=Kind.LOGIN_FAILURE, key=key)
        raise InvalidCredentials()

    AuthAttempt.objects.filter(key=key, kind=Kind.LOGIN_FAILURE).delete()
    update_last_login(None, user)
    return user


# --------------------------------------------------------------------------
# Password reset (also how members who joined before passwords existed set one)
# --------------------------------------------------------------------------


def password_reset_link(user: User) -> str:
    token = default_token_generator.make_token(user)
    # In the fragment, not the query string: browsers never send it to the
    # server, so it stays out of access logs and Referer headers.
    return f"{settings.FRONTEND_URL}/reset-password#uid={user.public_id}&token={token}"


def request_password_reset(email: str) -> None:
    """
    Email a reset link if `email` belongs to an active member. Returns the same
    way whether or not it does. Raises PasswordResetUnavailable when email can't
    be delivered, and PasswordResetRateLimited for too many requests.
    """
    if not email_configured():
        raise PasswordResetUnavailable()

    email = normalize_email(email)
    key = _attempt_key(email)
    # Counted for every address, registered or not, so the limit reveals nothing.
    _check_limit(
        key,
        Kind.PASSWORD_RESET,
        settings.PASSWORD_RESET_MAX_PER_HOUR,
        timedelta(hours=1),
        PasswordResetRateLimited,
    )
    AuthAttempt.objects.create(kind=Kind.PASSWORD_RESET, key=key)

    user = _member_with_email(email)
    if user is None:
        return

    body = (
        f"{_greeting(user)}\n\n"
        f"We received a request to set a new password for your {SITE_NAME} account.\n"
        f"To choose your password, open this link within {_duration(settings.PASSWORD_RESET_TIMEOUT)}:\n\n"
        f"{password_reset_link(user)}\n\n"
        "The link works once. If you didn't ask for this, you can ignore this email: "
        "your password won't change.\n\n"
        f"{SITE_NAME}\n"
    )
    try:
        send_email(user.email, f"Set your {SITE_NAME} password", body)
    except EmailError as exc:
        # Not reported to the visitor: that would reveal the address is registered.
        logger.error("Password reset email not sent to user %s: %s", user.public_id, exc)


def find_reset_user(uid, token: str) -> User:
    """The member a reset link belongs to. Raises PasswordResetLinkInvalid if it can't be used."""
    user = User.objects.filter(public_id=uid, is_active=True, role=Role.MEMBER).first()
    if user is None or not default_token_generator.check_token(user, token):
        raise PasswordResetLinkInvalid()
    return user


def reset_password(uid, token: str, new_password: str) -> User:
    """
    Set a new password from a reset link and sign the member out everywhere.
    Raises PasswordResetLinkInvalid, or django ValidationError for a weak password.
    """
    user = find_reset_user(uid, token)
    validate_password(new_password, user)

    with transaction.atomic():
        user.set_password(new_password)
        update_fields = ["password"]
        if user.email_verified_at is None:
            # Opening the emailed link proves the member controls this address.
            user.email_verified_at = timezone.now()
            update_fields.append("email_verified_at")
        user.save(update_fields=update_fields)
        AuthAttempt.objects.filter(key=_attempt_key(user.email), kind=Kind.LOGIN_FAILURE).delete()
        _end_all_sessions(user)

    body = (
        f"{'Hello ' + user.first_name + ',' if user.first_name else 'Hello,'}\n\n"
        f"The password for your {SITE_NAME} account was just changed, and you have been "
        "signed out on all devices.\n\n"
        "If you didn't do this, reset your password straight away from the login page "
        "and contact us.\n\n"
        f"{SITE_NAME}\n"
    )
    try:
        send_email(user.email, f"Your {SITE_NAME} password was changed", body)
    except EmailError as exc:
        logger.error("Password-changed email not sent to user %s: %s", user.public_id, exc)
    return user


def purge_old_attempts(older_than=timedelta(days=1)) -> int:
    """Delete attempt records older than every limit window. Returns the number deleted."""
    deleted, _ = AuthAttempt.objects.filter(created_at__lt=timezone.now() - older_than).delete()
    return deleted
