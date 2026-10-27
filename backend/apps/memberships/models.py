"""
Membership packages and member subscriptions to them.

MembershipPackage is the one place package terms live: the public package
list, the member dashboard, the admin and the entitlement checks all read it.

Subscriptions are activated either by staff in the Django admin after an
offline payment, or by apps.payments once Razorpay confirms a captured
payment on the server. A subscription is never activated by the member's
browser. Each subscription keeps the fee, validity
and contact limit it was recorded with, so editing a package later never
changes what an existing member bought.
"""
import calendar
import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

from .plans import PackageCode, PlanCode


def add_months(start: datetime, months: int) -> datetime:
    """
    The same day and time `months` calendar months later, counted in the site's
    time zone (TIME_ZONE, India), not UTC: 10:00 on 30 November plus three
    months is 10:00 on 28 February. A day the end month doesn't have becomes
    its last day (31 January + 1 month = 28 or 29 February).
    """
    aware = timezone.is_aware(start)
    local = timezone.localtime(start) if aware else start
    month = local.month - 1 + months
    year = local.year + month // 12
    month = month % 12 + 1
    day = min(local.day, calendar.monthrange(year, month)[1])
    end = local.replace(year=year, month=month, day=day)
    # Re-attach the zone for the new date (DST-safe), then back to the caller's zone.
    return timezone.make_aware(end.replace(tzinfo=None)).astimezone(start.tzinfo) if aware else end


def configured_gst_rate() -> Decimal | None:
    """settings.MEMBERSHIP_GST_RATE_PERCENT as a Decimal, or None when unset or not a valid percentage."""
    raw = settings.MEMBERSHIP_GST_RATE_PERCENT
    if not raw:
        return None
    try:
        rate = Decimal(str(raw))
    except InvalidOperation:
        return None
    return rate if rate.is_finite() and Decimal("0") <= rate <= Decimal("100") else None


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
    def gst_rate(self) -> Decimal | None:
        """
        The GST rate (percent) this package's price uses: its stated rate, or for
        "plus applicable GST" packages settings.MEMBERSHIP_GST_RATE_PERCENT. None
        while that isn't confirmed, so no total can be calculated or charged.
        """
        if self.tax_treatment == TaxTreatment.GST_STATED:
            return self.stated_gst_rate
        if self.tax_treatment == TaxTreatment.GST_EXTRA:
            return configured_gst_rate()
        return None

    @property
    def gst_amount(self) -> Decimal | None:
        """GST in rupees, rounded to the paisa (half up); None while the rate is unknown."""
        rate = self.gst_rate
        if rate is None:
            return None
        return (self.fee * rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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


class AssistanceStatus(models.TextChoices):
    # Waiting for staff to assign a matchmaker.
    REQUESTED = "requested", "Awaiting assignment"
    ASSIGNED = "assigned", "Matchmaker assigned"
    IN_PROGRESS = "in_progress", "In progress"
    AWAITING_MEMBER = "awaiting_member", "Awaiting member response"
    FOLLOW_UP = "follow_up", "Follow-up scheduled"
    ON_HOLD = "on_hold", "On hold"
    COMPLETED = "completed", "Completed"
    # Staff couldn't offer the service for this request.
    UNAVAILABLE = "unavailable", "Unavailable"
    CANCELLED = "cancelled", "Cancelled"
    # Closed by staff because the membership's service period ended.
    EXPIRED = "expired", "Expired"
    # Stages of the Royal service (apps.memberships.assistance.ROYAL_STATUSES).
    REQUIREMENTS = "requirements", "Requirements gathering"
    CURATION = "curation", "Profile curation"
    AWAITING_REVIEW = "awaiting_review", "Awaiting member review"
    FAMILY = "family", "Family coordination"
    CONSULTATION_REQUESTED = "consult_requested", "Consultation requested"
    CONSULTATION_SCHEDULED = "consult_scheduled", "Consultation scheduled"


OPEN_ASSISTANCE_STATUSES = (
    AssistanceStatus.REQUESTED, AssistanceStatus.ASSIGNED, AssistanceStatus.IN_PROGRESS,
    AssistanceStatus.AWAITING_MEMBER, AssistanceStatus.FOLLOW_UP, AssistanceStatus.ON_HOLD,
    AssistanceStatus.REQUIREMENTS, AssistanceStatus.CURATION, AssistanceStatus.AWAITING_REVIEW,
    AssistanceStatus.FAMILY, AssistanceStatus.CONSULTATION_REQUESTED, AssistanceStatus.CONSULTATION_SCHEDULED,
)
# Statuses that only make sense with a matchmaker assigned.
ASSIGNED_STATUSES = (
    AssistanceStatus.ASSIGNED, AssistanceStatus.IN_PROGRESS, AssistanceStatus.AWAITING_MEMBER,
    AssistanceStatus.FOLLOW_UP, AssistanceStatus.COMPLETED, AssistanceStatus.REQUIREMENTS,
    AssistanceStatus.CURATION, AssistanceStatus.AWAITING_REVIEW, AssistanceStatus.FAMILY,
    AssistanceStatus.CONSULTATION_REQUESTED, AssistanceStatus.CONSULTATION_SCHEDULED,
)


class AssistanceKind(models.TextChoices):
    # A Gold or Diamond member asked for help (apps.memberships.assistance.request_assistance).
    REQUEST = "request", "Assistance request"
    # The Platinum service itself, opened when the membership is activated (open_service_case).
    SERVICE = "service", "Assisted matchmaking case"


class AssistanceRequest(TimeStampedModel):
    """
    A matchmaking-assistance case (apps.memberships.assistance): a Gold or Diamond
    member's request, or a Platinum member's assisted-matchmaking service.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    kind = models.CharField(max_length=8, choices=AssistanceKind.choices, default=AssistanceKind.REQUEST, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assistance_requests")
    # The membership that included the service. A service case covers that membership's period.
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="assistance_requests")
    status = models.CharField(
        max_length=17, choices=AssistanceStatus.choices, default=AssistanceStatus.REQUESTED, db_index=True
    )
    member_note = models.TextField(
        max_length=1000, blank=True,
        help_text="What the member would like help with: their own words (a service-case member can update them).",
    )
    member_note_updated_at = models.DateTimeField(null=True, blank=True)
    # Staff recommendations, kept apart from the member's own requirements. Both shown to the member.
    service_plan = models.TextField(
        blank=True, help_text="The agreed service plan and priorities. Shown to the member."
    )
    next_steps = models.TextField(blank=True, help_text="Agreed next steps. Shown to the member.")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_assistance",
        limit_choices_to={"is_staff": True, "is_active": True},
        help_text="The matchmaker handling this case: an active staff account allowed to handle cases.",
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    member_message = models.CharField(
        max_length=300, blank=True, help_text="Shown to the member, e.g. why the service is unavailable."
    )
    staff_note = models.TextField(blank=True, help_text="Internal; never shown to the member.")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status"])]
        permissions = [
            ("assign_assistancerequest", "Can see every matchmaking case and assign matchmakers"),
        ]
        verbose_name = "matchmaking case"

    def __str__(self):
        return f"{self.get_kind_display()} for {self.user}"

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_ASSISTANCE_STATUSES

    @property
    def service_active(self) -> bool:
        """The membership that includes the service is current (active and inside its period)."""
        return self.subscription.is_current


class AssistanceEvent(models.Model):
    """One status or assignment change of an AssistanceRequest. Append-only."""

    request = models.ForeignKey(AssistanceRequest, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=17, choices=AssistanceStatus.choices)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    # Who made the change: the member (when asking) or a staff member.
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.get_status_display()} at {self.created_at:%d %b %Y %H:%M}"



class AssistanceNote(models.Model):
    """A matchmaker's note on a case: internal, or a progress update the member sees."""

    request = models.ForeignKey(AssistanceRequest, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    body = models.TextField(max_length=2000)
    visible_to_member = models.BooleanField(
        default=False, help_text="Show this to the member as a progress update. Unticked notes stay internal."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name = "case note"

    def __str__(self):
        return "Progress update" if self.visible_to_member else "Internal note"


class FollowUpStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    DONE = "done", "Done"
    CANCELLED = "cancelled", "Cancelled"


class AssistanceFollowUp(TimeStampedModel):
    """A follow-up action on a case, as recorded by staff."""

    request = models.ForeignKey(AssistanceRequest, on_delete=models.CASCADE, related_name="follow_ups")
    action = models.CharField(max_length=200, help_text="What will be done. The member sees this when shown to them.")
    due_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=FollowUpStatus.choices, default=FollowUpStatus.SCHEDULED)
    awaiting_member = models.BooleanField(default=False, help_text="Waiting for the member's response.")
    outcome = models.TextField(blank=True, help_text="Internal: what happened.")
    visible_to_member = models.BooleanField(default=False, help_text="Show the action, date and status to the member.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_on", "pk"]
        verbose_name = "follow-up"

    def __str__(self):
        return self.action


class CandidateResponse(models.TextChoices):
    PENDING = "pending", "No response yet"
    INTERESTED = "interested", "Interested"
    NOT_INTERESTED = "not_interested", "Not interested"


class AssistanceCandidate(TimeStampedModel):
    """A profile a matchmaker found for the case member; shown to the member once staff share it."""

    request = models.ForeignKey(AssistanceRequest, on_delete=models.CASCADE, related_name="candidates")
    profile = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="+")
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    staff_note = models.TextField(blank=True, help_text="Internal; never shown to either member.")
    shared_with_member = models.BooleanField(default=False, help_text="Show this profile to the member as a suggestion.")
    shared_at = models.DateTimeField(null=True, blank=True)
    member_response = models.CharField(
        max_length=16, choices=CandidateResponse.choices, default=CandidateResponse.PENDING
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["request", "profile"], name="unique_case_candidate")]
        verbose_name = "suggested profile"

    def __str__(self):
        return f"Suggested profile {self.profile_id}"


class ExchangeStatus(models.TextChoices):
    PENDING = "pending", "Pending consent"
    # Both members consented: each may now see the other's mobile number.
    SHARED = "shared", "Shared"
    # A member declined or withdrew consent before both had agreed.
    DECLINED = "declined", "Declined"
    CANCELLED = "cancelled", "Cancelled"


class ContactExchange(TimeStampedModel):
    """
    A matchmaker-coordinated exchange of mobile numbers between a service case's
    member and one other member, which happens only once both consent
    (apps.memberships.assistance). No number is stored here.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    request = models.ForeignKey(AssistanceRequest, on_delete=models.PROTECT, related_name="exchanges")
    other_profile = models.ForeignKey("profiles.Profile", on_delete=models.PROTECT, related_name="+")
    purpose = models.CharField(max_length=300, help_text="Why the numbers would be shared. Both members see this.")
    status = models.CharField(max_length=10, choices=ExchangeStatus.choices, default=ExchangeStatus.PENDING, db_index=True)
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    shared_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "contact exchange"

    def __str__(self):
        return f"Contact exchange {self.public_id}"


class ConsentDecision(models.TextChoices):
    PENDING = "pending", "Awaiting decision"
    GRANTED = "granted", "Consented"
    DECLINED = "declined", "Declined"
    WITHDRAWN = "withdrawn", "Withdrawn"


class ContactConsent(models.Model):
    """One member's decision on a ContactExchange, with the exact statement they were shown."""

    exchange = models.ForeignKey(ContactExchange, on_delete=models.CASCADE, related_name="consents")
    profile = models.ForeignKey("profiles.Profile", on_delete=models.PROTECT, related_name="+")
    statement = models.TextField()
    decision = models.CharField(max_length=10, choices=ConsentDecision.choices, default=ConsentDecision.PENDING)
    decided_at = models.DateTimeField(null=True, blank=True)
    # When this member was first shown the other member's number (the disclosure record).
    number_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["pk"]
        constraints = [models.UniqueConstraint(fields=["exchange", "profile"], name="unique_exchange_consent")]

    def __str__(self):
        return self.get_decision_display()


class ConsultationStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    # Staff proposed a date and time; not scheduled until the member confirms it.
    PROPOSED = "proposed", "Time proposed, awaiting your confirmation"
    SCHEDULED = "scheduled", "Scheduled"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"
    # No home visit can be offered (e.g. no staff capacity or coverage for the area).
    UNAVAILABLE = "unavailable", "Home visit unavailable"


OPEN_CONSULTATION_STATUSES = (ConsultationStatus.REQUESTED, ConsultationStatus.PROPOSED, ConsultationStatus.SCHEDULED)


class Consultation(TimeStampedModel):
    """An at-home consultation on a Royal case (apps.memberships.assistance). Never scheduled automatically."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    request = models.ForeignKey(AssistanceRequest, on_delete=models.CASCADE, related_name="consultations")
    status = models.CharField(
        max_length=12, choices=ConsultationStatus.choices, default=ConsultationStatus.REQUESTED, db_index=True
    )
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    member_note = models.CharField(max_length=500, blank=True, help_text="Preferred days or times, from the member.")
    # Restricted: only the case's staff see it; member APIs say only whether one was given.
    address = models.TextField(max_length=500, blank=True, help_text="Where the visit would take place. Restricted.")
    scheduled_for = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    member_message = models.CharField(max_length=300, blank=True, help_text="Shown to the member.")
    outcome = models.TextField(blank=True, help_text="Internal: what happened at the visit.")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Consultation ({self.get_status_display()})"

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_CONSULTATION_STATUSES


class ConsultationEvent(models.Model):
    """One status change (including each reschedule) of a Consultation. Append-only."""

    consultation = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=12, choices=ConsultationStatus.choices)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]


class FamilyPermission(models.TextChoices):
    PENDING = "pending", "Awaiting the member's permission"
    GRANTED = "granted", "Permitted"
    WITHDRAWN = "withdrawn", "Withdrawn"


class FamilyContact(TimeStampedModel):
    """
    A family member the Royal member permits the matchmaker to coordinate with,
    for a stated purpose. Only the member grants permission, and may withdraw it.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    request = models.ForeignKey(AssistanceRequest, on_delete=models.CASCADE, related_name="family_contacts")
    name = models.CharField(max_length=80)
    relationship = models.CharField(max_length=40)
    # Only what's needed to coordinate. Restricted to the case's staff and the member.
    phone_number = models.CharField(max_length=20, blank=True)
    purpose = models.CharField(max_length=300, help_text="What the matchmaker may coordinate with this person.")
    permission = models.CharField(
        max_length=10, choices=FamilyPermission.choices, default=FamilyPermission.PENDING, db_index=True
    )
    # The exact text the member agreed to.
    statement = models.TextField(blank=True)
    granted_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name = "family contact"

    def __str__(self):
        return f"{self.name} ({self.relationship})"


class FamilyCoordination(models.Model):
    """A coordination action with a permitted family contact, as recorded by staff."""

    contact = models.ForeignKey(FamilyContact, on_delete=models.CASCADE, related_name="actions")
    action = models.CharField(max_length=300)
    outcome = models.TextField(blank=True, help_text="Internal.")
    visible_to_member = models.BooleanField(default=False, help_text="Show the action (not the outcome) to the member.")
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name = "family coordination action"

    def __str__(self):
        return self.action
