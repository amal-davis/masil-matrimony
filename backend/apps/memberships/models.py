"""
Member subscriptions to the packages in plans.py.

There is no payment gateway yet, so subscriptions are recorded and activated
by staff in the Django admin after an offline payment. A subscription is never
activated by the member's browser.
"""
import calendar
import uuid
from datetime import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

from .plans import PLANS, PlanCode


def add_months(start: datetime, months: int) -> datetime:
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


class SubscriptionStatus(models.TextChoices):
    # Recorded by staff but not yet paid/confirmed. Grants nothing.
    PENDING = "pending", "Pending activation"
    ACTIVE = "active", "Active"
    CANCELLED = "cancelled", "Cancelled"


class SubscriptionQuerySet(models.QuerySet):
    def current(self):
        """Active subscriptions whose period includes now."""
        now = timezone.now()
        return self.filter(status=SubscriptionStatus.ACTIVE, starts_at__lte=now, ends_at__gt=now)


class Subscription(TimeStampedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="subscriptions")
    plan_code = models.CharField(max_length=16, choices=PlanCode.choices)
    status = models.CharField(
        max_length=10, choices=SubscriptionStatus.choices, default=SubscriptionStatus.PENDING, db_index=True
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    contact_views_used = models.PositiveIntegerField(default=0)
    staff_note = models.CharField(max_length=255, blank=True, help_text="Internal; never shown to the member.")
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = SubscriptionQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status", "ends_at"])]

    def __str__(self):
        return f"{self.get_plan_code_display()} for {self.user}"

    @property
    def plan(self):
        return PLANS[self.plan_code]

    @property
    def is_current(self) -> bool:
        now = timezone.now()
        return (
            self.status == SubscriptionStatus.ACTIVE
            and self.starts_at is not None
            and self.ends_at is not None
            and self.starts_at <= now < self.ends_at
        )

    @property
    def display_status(self) -> str:
        """What the member sees: active, expired, upcoming, pending or cancelled."""
        if self.status != SubscriptionStatus.ACTIVE:
            return self.status
        now = timezone.now()
        if self.ends_at and self.ends_at <= now:
            return "expired"
        if self.starts_at and self.starts_at > now:
            return "upcoming"
        return "active"

    def activate(self, by=None, starts_at=None):
        """Start the plan's validity period now (or at `starts_at`)."""
        self.status = SubscriptionStatus.ACTIVE
        self.starts_at = starts_at or self.starts_at or timezone.now()
        self.ends_at = add_months(self.starts_at, self.plan.validity_months)
        self.activated_by = by
