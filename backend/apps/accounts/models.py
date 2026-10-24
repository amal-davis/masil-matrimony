import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from .managers import UserManager
from .roles import STAFF_ROLES, Role

phone_validator = RegexValidator(
    regex=r"^\+[1-9]\d{6,14}$",
    message="Enter the phone number in international format, e.g. +919876543210.",
)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Account used by members and staff alike. Profile data lives in the
    profiles app; this model holds only identity and access information.
    """

    # Exposed to clients and in tokens instead of the sequential primary key.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(unique=True, max_length=254)
    phone_number = models.CharField(
        max_length=16, unique=True, null=True, blank=True, validators=[phone_validator]
    )
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(
        max_length=32, choices=Role.choices, default=Role.MEMBER, db_index=True
    )

    is_active = models.BooleanField(default=True)
    # Grants access to the Django admin site only; API access is governed by role.
    is_staff = models.BooleanField(default=False)
    # Members can't sign in or use member APIs until this is set (apps.accounts.email_verification).
    # Separate from is_active, which is the administrator's suspension switch.
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # When the newest verification link was issued; earlier links stop working.
    email_verification_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-date_joined"]
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email).lower()
        if self.phone_number == "":
            self.phone_number = None
        if self.role == Role.MEMBER and (self.is_staff or self.is_superuser):
            raise ValidationError("Members cannot have staff or superuser access.")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_member(self):
        return self.role == Role.MEMBER

    @property
    def is_platform_staff(self):
        return self.role in STAFF_ROLES

    def has_role(self, *roles):
        return self.is_active and self.role in roles


class PhoneOTPChallenge(models.Model):
    """
    One one-time code sent (or, for unknown numbers, pretended to be sent) by SMS.

    The code itself is never stored: `code_hash` is an HMAC bound to this
    challenge, its purpose and its phone number (see apps.accounts.otp).
    A challenge is usable once, until it expires, is replaced by a newer code
    for the same number, or has too many wrong guesses.
    """

    class Purpose(models.TextChoices):
        LOGIN = "login", "Login"

    # The opaque reference the client sends back with the code.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    purpose = models.CharField(max_length=16, choices=Purpose.choices)
    phone_number = models.CharField(max_length=16)
    # Null when no eligible account has this number: nothing is sent and verification always fails.
    user = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["phone_number", "purpose", "created_at"])]
        verbose_name = "phone OTP challenge"

    def __str__(self):
        return f"{self.purpose} code for …{self.phone_number[-4:]}"


class AuthAttempt(models.Model):
    """
    A failed password login, a password-reset request or a verification email, for one email address.
    Counted per address over a time window (see apps.accounts.password_auth) so
    the limits hold across API processes, like the SMS limits above.

    The address itself is not stored: `key` is an HMAC of the normalised email,
    so the table holds no personal data even for addresses typed by attackers.
    """

    class Kind(models.TextChoices):
        LOGIN_FAILURE = "login_failure", "Failed login"
        PASSWORD_RESET = "password_reset", "Password reset request"
        VERIFICATION_EMAIL = "verify_email", "Verification email"

    kind = models.CharField(max_length=16, choices=Kind.choices)
    key = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["key", "kind", "created_at"])]
        verbose_name = "authentication attempt"

    def __str__(self):
        return f"{self.kind} at {self.created_at:%Y-%m-%d %H:%M}"
