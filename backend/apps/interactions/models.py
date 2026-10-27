"""
Member-to-member activity: interests sent/accepted/declined, shortlists,
paid contact-number views, profile views and personal messages. Blocks and
reports are planned (docs/database-design.md).
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
    # Sent while the sender had no current paid subscription, so it counts toward the
    # Free package's total interest limit. Set once; re-sending after a withdrawal doesn't count again.
    counts_toward_free_limit = models.BooleanField(default=False)

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


class ContactView(models.Model):
    """
    A member viewed another member's mobile number under a paid subscription.
    Limits count different members per subscription, so viewing the same
    number again during the subscription is free and adds no row.
    """

    subscription = models.ForeignKey(
        "memberships.Subscription", on_delete=models.PROTECT, related_name="contact_views"
    )
    viewer = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="contact_views_made")
    profile = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="contact_views_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["subscription", "profile"], name="one_contact_view_per_subscription"),
            models.CheckConstraint(condition=~Q(viewer=F("profile")), name="no_contact_view_of_self"),
        ]

    def __str__(self):
        return f"{self.viewer.profile_code} viewed {self.profile.profile_code}'s number"


class ProfileView(models.Model):
    """
    A member opened another member's profile page (apps.interactions.profile_views).
    One row per (viewer, profile): later visits update it, and a visit counts again
    only after VISIT_GAP, so reloads and repeated rendering aren't new views.
    """

    viewer = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="profile_views_made")
    profile = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="profile_views_received")
    first_viewed_at = models.DateTimeField()
    last_viewed_at = models.DateTimeField()
    visits = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-last_viewed_at"]
        constraints = [
            models.UniqueConstraint(fields=["viewer", "profile"], name="one_profile_view_per_pair"),
            models.CheckConstraint(condition=~Q(viewer=F("profile")), name="no_profile_view_of_self"),
        ]
        indexes = [models.Index(fields=["profile", "last_viewed_at"])]

    def __str__(self):
        return f"{self.viewer.profile_code} viewed {self.profile.profile_code}"


class Conversation(TimeStampedModel):
    """
    Personal messages between two members (apps.interactions.messaging). One per
    pair: `member_a` is always the profile with the lower id, so the pair is unique
    whoever writes first.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    member_a = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="+")
    member_b = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="+")
    # Who wrote first. Starting a conversation needs the messaging benefit; the other member may reply.
    started_by = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="+")
    last_message_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-last_message_at"]
        constraints = [
            models.UniqueConstraint(fields=["member_a", "member_b"], name="one_conversation_per_pair"),
            models.CheckConstraint(condition=Q(member_a__lt=F("member_b")), name="conversation_members_ordered"),
        ]

    def __str__(self):
        return f"Conversation {self.public_id}"

    def other(self, profile):
        return self.member_b if profile.pk == self.member_a_id else self.member_a


class Message(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="messages_sent")
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # When the other member opened the conversation after this message arrived.
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["conversation", "sender", "read_at"])]

    def __str__(self):
        return f"Message {self.public_id}"
