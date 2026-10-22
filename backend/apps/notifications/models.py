"""
In-app, email, SMS and push notifications, delivery status and member
notification preferences. SMS/OTP providers are configured via environment.

Only in-app notifications exist so far (apps.notifications.services.notify).
"""
import uuid

from django.conf import settings
from django.db import models


class NotificationKind(models.TextChoices):
    INTEREST_RECEIVED = "interest_received", "Interest received"
    INTEREST_ACCEPTED = "interest_accepted", "Interest accepted"
    INTEREST_DECLINED = "interest_declined", "Interest declined"
    PROFILE_APPROVED = "profile_approved", "Profile approved"
    PROFILE_CHANGES_REQUESTED = "profile_changes_requested", "Profile changes requested"
    PHOTO_APPROVED = "photo_approved", "Photo approved"
    PHOTO_REJECTED = "photo_rejected", "Photo rejected"
    MEMBERSHIP_ACTIVATED = "membership_activated", "Membership activated"


class Notification(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=32, choices=NotificationKind.choices)
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=300, blank=True)
    # A site path such as "/dashboard/interests/received"; never an external URL.
    link = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "read_at", "created_at"])]

    def __str__(self):
        return f"{self.kind} for {self.recipient}"
