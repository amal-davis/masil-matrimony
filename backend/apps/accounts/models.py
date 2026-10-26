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
    # Staff sign in to the admin site with their email and password, so staff need one.
    # For members it is optional contact information: they sign in with an SMS code
    # sent to `phone_number` (apps.accounts.otp). NULL, not "", when absent (unique).
    email = models.EmailField(unique=True, max_length=254, null=True, blank=True)
    # E.164. How members sign in; unique, so one mobile number is one account.
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
    # Historical: set when a member opened an emailed verification link, which
    # registration no longer requires. Kept as information; it grants nothing.
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # Historical: when the newest verification link was emailed. No longer written.
    email_verification_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    # When the member proved they receive SMS at `phone_number` (a correct one-time
    # code). Members can't sign in or use member APIs until this is set
    # (apps.accounts.permissions); it is cleared whenever the number changes.
    # Separate from is_active, which is the administrator's suspension switch.
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
        return self.email or self.phone_number or str(self.public_id)

    @classmethod
    def from_db(cls, db, field_names, values):
        user = super().from_db(db, field_names, values)
        user._loaded_phone_number = user.__dict__.get("phone_number")
        return user

    def save(self, *args, **kwargs):
        # A verification proves possession of one number only: a changed number must be proved again.
        update_fields = kwargs.get("update_fields")
        loaded = getattr(self, "_loaded_phone_number", self.phone_number)
        if loaded != self.phone_number and (update_fields is None or "phone_number" in update_fields):
            self.phone_verified_at = None
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "phone_verified_at"}
        super().save(*args, **kwargs)
        self._loaded_phone_number = self.phone_number

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email).lower() if self.email else None
        if self.phone_number == "":
            self.phone_number = None
        if self.role == Role.MEMBER and (self.is_staff or self.is_superuser):
            raise ValidationError("Members cannot have staff or superuser access.")
        if self.role != Role.MEMBER and not self.email:
            raise ValidationError({"email": "Staff accounts need an email address to sign in."})

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
    One one-time code sent (or, for unknown numbers at login, pretended to be sent) by SMS.

    The code itself is never stored: `code_hash` is an HMAC bound to this
    challenge, its purpose and its phone number (see apps.accounts.otp).
    A challenge is usable once, until it expires, is replaced by a newer code
    for the same number, or has too many wrong guesses.

    A registration challenge carries the registration details in `registration`.
    The account is created from them only when the code is verified, so an
    unverified registration never becomes an account; the details are deleted
    with the challenge by purge_otp_challenges.
    """

    class Purpose(models.TextChoices):
        LOGIN = "login", "Login"
        REGISTER = "register", "Registration"

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
    # Registration only: the validated details awaiting verification (apps.accounts.registration).
    registration = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["phone_number", "purpose", "created_at"])]
        verbose_name = "phone OTP challenge"

    def __str__(self):
        return f"{self.purpose} code for …{self.phone_number[-4:]}"


class OTPNumberLock(models.Model):
    """
    One row per mobile number that requested a code recently, locked (SELECT ...
    FOR UPDATE) while a code is issued, so simultaneous requests for the same
    number run one after another and can't both get past the cooldown.
    `key` is an HMAC of the number, so the table holds no phone numbers.
    """

    key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "OTP number lock"

    def __str__(self):
        return self.key[:12]


class AuthAttempt(models.Model):
    """
    Historical: failed password logins, password-reset requests and verification
    emails, from when members signed in with an email address and password.
    Nothing records new attempts; purge_auth_attempts removes the old rows.

    The address itself is not stored: `key` is an HMAC of the normalised email.
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
