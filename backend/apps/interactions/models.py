"""
Member-to-member activity: interests sent/accepted/declined and shortlists.
Profile views, blocks and reports are planned (docs/database-design.md).
"""
import uuid

from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel


class InterestStatus(models.TextChoices):
    PENDING = "pending", "Awaiting response"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    WITHDRAWN = "withdrawn", "Withdrawn"


class Interest(TimeStampedModel):
    """One member's interest in another. At most one per (sender, receiver) pair."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    sender = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="interests_sent")
    receiver = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="interests_received")
    status = models.CharField(max_length=10, choices=InterestStatus.choices, default=InterestStatus.PENDING)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["sender", "receiver"], name="one_interest_per_pair"),
            models.CheckConstraint(condition=~Q(sender=F("receiver")), name="no_interest_in_self"),
        ]
        indexes = [
            models.Index(fields=["receiver", "status", "created_at"]),
            models.Index(fields=["sender", "status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.sender.profile_code} → {self.receiver.profile_code} ({self.status})"


class Shortlist(models.Model):
    owner = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="shortlist_entries")
    profile = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="shortlisted_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "profile"], name="one_shortlist_entry_per_pair"),
            models.CheckConstraint(condition=~Q(owner=F("profile")), name="no_shortlisting_self"),
        ]

    def __str__(self):
        return f"{self.owner.profile_code} shortlisted {self.profile.profile_code}"
