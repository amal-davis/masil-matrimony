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
    email_verified_at = models.DateTimeField(null=True, blank=True)
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
