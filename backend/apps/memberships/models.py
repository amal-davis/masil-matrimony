"""
Membership packages and member subscriptions to them.

MembershipPackage is the one place package terms live: the public package
list, the member dashboard, the admin and the entitlement checks all read it.

There is no payment gateway yet, so subscriptions are recorded and activated
by staff in the Django admin after an offline payment. A subscription is never
activated by the member's browser. Each subscription keeps the fee, validity
and contact limit it was recorded with, so editing a package later never
changes what an existing member bought.
"""
import calendar
import uuid
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

from .plans import PackageCode, PlanCode


def add_months(start: datetime, months: int) -> datetime:
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


class PackageCategory(models.TextChoices):
    ONLINE = "online", "Online membership"
    ASSISTED = "assisted", "Assisted matchmaking"


class TaxTreatment(models.TextChoices):
    NO_FEE = "no_fee", "No fee"
    # The fee excludes GST. No rate is configured for checkout, so no total is calculated.
    GST_EXTRA = "gst_extra", "Fee plus applicable GST"
    # The published price states a GST rate; total = fee + fee × rate.
    GST_STATED = "gst_stated", "GST included at the stated rate"


class MembershipPackageQuerySet(models.QuerySet):
    def available(self):
        return self.filter(is_available=True)


class MembershipPackage(TimeStampedModel):
    code = models.CharField(max_length=16, choices=PackageCode.choices, unique=True)
    category = models.CharField(max_length=10, choices=PackageCategory.choices)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_available = models.BooleanField(
        default=True, help_text="Shown on the website and can be recorded for members. Existing subscriptions are kept."
    )

    # Copy shown on the website.
    name = models.CharField(max_length=80)
    subtitle = models.CharField(max_length=80, blank=True)
    tagline = models.CharField(max_length=120, blank=True)
    service_label = models.CharField(max_length=40, help_text='Short service type, e.g. "Online Membership".')
    description = models.TextField()
    benefits = models.JSONField(
        default=list,
        blank=True,
        help_text='A list of {"title": "…", "detail": "…"} objects; "detail" is optional.',
    )
    terms_title = models.CharField(max_length=80)
    terms_body = models.TextField()
    cta_label = models.CharField(max_length=40)

    # Commercial terms. Only people with "Can change package terms" may edit these.
    fee = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))],
        help_text="Base fee in rupees, excluding GST.",
    )
    fee_label = models.CharField(max_length=40, default="Membership fee", help_text='e.g. "Annual service fee".')
    tax_treatment = models.CharField(max_length=12, choices=TaxTreatment.choices)
    stated_gst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Percent. Only for packages whose published price includes GST at a stated rate.",
    )
    validity_months = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Months from activation. Empty for Free, which doesn't expire."
    )
    contact_view_limit = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Different members' contact numbers viewable per subscription. Empty = not a self-service benefit.",
    )
    outgoing_interest_limit = models.PositiveIntegerField(
        null=True, blank=True, help_text="Total interests a member may send on this package. Empty = unlimited."
    )

    objects = MembershipPackageQuerySet.as_manager()

    COMMERCIAL_FIELDS = (
        "fee", "tax_treatment", "stated_gst_rate", "validity_months", "contact_view_limit", "outgoing_interest_limit",
    )

    class Meta:
        ordering = ["display_order", "pk"]
        permissions = [("change_package_terms", "Can change package fees, tax, validity and limits")]

    def __str__(self):
        return self.name

    @property
    def is_free(self) -> bool:
        return self.code == PackageCode.FREE

    @property
    def gst_amount(self) -> Decimal | None:
        """GST in rupees when the package states a rate; None when GST is extra at the applicable rate."""
        if self.tax_treatment != TaxTreatment.GST_STATED or self.stated_gst_rate is None:
            return None
        return (self.fee * self.stated_gst_rate / 100).quantize(Decimal("0.01"))

    @property
    def total_payable(self) -> Decimal | None:
        """The amount to pay, or None when it depends on a GST rate the backend doesn't know."""
        if self.tax_treatment == TaxTreatment.NO_FEE:
            return Decimal("0.00")
        gst = self.gst_amount
        return None if gst is None else self.fee + gst

    def clean(self):
        errors = {}
        if self.is_free:
            if self.fee != 0 or self.tax_treatment != TaxTreatment.NO_FEE:
                errors["fee"] = "The Free package has no fee."
            if self.validity_months is not None:
                errors["validity_months"] = "Free membership doesn't expire; leave validity empty."
        else:
            if not self.validity_months:
                errors["validity_months"] = "Paid packages need a validity period."
            if self.tax_treatment == TaxTreatment.NO_FEE:
                errors["tax_treatment"] = "Only the Free package has no fee."
        if not self.is_free and self.outgoing_interest_limit is not None:
            # Interest limits are counted for Free members only (see apps.interactions.services).
            errors["outgoing_interest_limit"] = "Only the Free package has an interest limit."
        if self.tax_treatment == TaxTreatment.GST_STATED and self.stated_gst_rate is None:
            errors["stated_gst_rate"] = "Enter the GST rate the published price includes."
        if self.tax_treatment != TaxTreatment.GST_STATED and self.stated_gst_rate is not None:
            errors["stated_gst_rate"] = "Only packages with a stated GST rate use this field."
        if not isinstance(self.benefits, list) or not all(
            isinstance(item, dict) and isinstance(item.get("title"), str) and item["title"].strip()
            and set(item) <= {"title", "detail"} and isinstance(item.get("detail", ""), str)
            for item in self.benefits
        ):
            errors["benefits"] = 'Use a list of {"title": "…", "detail": "…"} objects.'
        if errors:
            raise ValidationError(errors)


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
    # Terms copied from the package when the subscription is recorded.
    package_fee = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Package fee excluding GST when recorded. Empty for subscriptions recorded before fees were stored.",
    )
    validity_months = models.PositiveSmallIntegerField(null=True, blank=True)
    contact_view_limit = models.PositiveIntegerField(null=True, blank=True)
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
    def plan(self) -> MembershipPackage:
        if getattr(self, "_plan", None) is None or self._plan.code != self.plan_code:
            self._plan = MembershipPackage.objects.get(code=self.plan_code)
        return self._plan

    def copy_package_terms(self):
        """Store the package's current terms on this subscription, once (validity is set exactly then)."""
        if self.validity_months is not None:
            return
        plan = self.plan
        self.package_fee = plan.fee
        self.validity_months = plan.validity_months
        self.contact_view_limit = plan.contact_view_limit

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.copy_package_terms()
        super().save(*args, **kwargs)

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
        """Start the validity period now (or at `starts_at`), using the validity stored on the subscription."""
        self.copy_package_terms()
        self.status = SubscriptionStatus.ACTIVE
        self.starts_at = starts_at or self.starts_at or timezone.now()
        self.ends_at = add_months(self.starts_at, self.validity_months)
        self.activated_by = by
