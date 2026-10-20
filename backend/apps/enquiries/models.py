"""
Public website enquiries and contact-form submissions before a visitor
becomes a registered member. See docs/database-design.md.
"""
import uuid

from django.conf import settings
from django.db import models

from apps.accounts.models import phone_validator
from apps.core.models import TimeStampedModel


class Enquiry(TimeStampedModel):
    """
    A message sent through a public form. Holds only what the visitor typed
    plus handling state for staff; no IP address or other tracking data.
    """

    class Source(models.TextChoices):
        CONTACT_FORM = "contact_form", "Contact form"

    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in_progress", "In progress"
        CLOSED = "closed", "Closed"

    # Exposed to clients instead of the sequential primary key.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254)
    # E.164, e.g. +919876543210 (normalised by the serializer).
    phone = models.CharField(max_length=16, validators=[phone_validator])
    message = models.TextField(max_length=2000)

    source = models.CharField(max_length=20, choices=Source.choices, default=Source.CONTACT_FORM)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_enquiries",
        limit_choices_to={"is_staff": True},
    )
    converted_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_enquiries",
        help_text="The member account this enquiry led to, if any.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "enquiries"

    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"
