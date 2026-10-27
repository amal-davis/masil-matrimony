"""
Membership Purchases in the admin. Payments here are records, not switches:
nothing marks a purchase paid, changes an amount, activates or extends a
membership, or refunds. The only way to "paid" is apps.payments.services.reconcile,
which asks Razorpay; staff can trigger that check ("Check status with Razorpay").
Refunds are made in Razorpay's dashboard and recorded here from Razorpay's
report. Each change of payment or refund status is kept in the purchase's history.

Permissions (besides view/change on Purchase):
- payments.view_purchase_financials: amounts, revenue figures and the summary's money cards;
- payments.export_purchase: the CSV export.
"""
import csv
import logging
from datetime import datetime

from django.contrib import admin, messages
from django.contrib.admin import DateFieldListFilter, SimpleListFilter
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from . import reporting, services
from .models import EventSource, Purchase, PurchaseEvent, RazorpayPayment, Receipt, WebhookEvent
from .razorpay_api import RazorpayError
from .receipts import send_receipt_email

logger = logging.getLogger(__name__)

FINANCIALS = "payments.view_purchase_financials"
EXPORT = "payments.export_purchase"


def rupees(value) -> str:
    return "—" if value is None else f"₹{value:,.2f}"


def local(value) -> str:
    return f"{timezone.localtime(value):%d %b %Y %H:%M}" if value else "—"


class ReadOnlyAdminMixin:
    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        # Change permission is kept (the actions need it), but no field can be edited.
        return [field.name for field in self.model._meta.fields] + list(getattr(self, "extra_readonly", []))


class RazorpayPaymentInline(ReadOnlyAdminMixin, TabularInline):
    model = RazorpayPayment
    extra = 0
    fields = ["payment_id", "status", "amount_subunits", "amount_refunded_subunits", "currency", "method",
              "error_description", "razorpay_created_at"]
    can_delete = False
    verbose_name_plural = "Payment attempts reported by Razorpay (amounts in paise)"

    def get_fields(self, request, obj=None):
        if request.user.has_perm(FINANCIALS):
            return self.fields
        return [name for name in self.fields if "amount" not in name]


class PurchaseEventInline(ReadOnlyAdminMixin, TabularInline):
    model = PurchaseEvent
    extra = 0
    fields = ["created_at", "status", "refund_status", "source", "staff", "note"]
    can_delete = False
    verbose_name_plural = "Payment status history"


class WebhookEventInline(ReadOnlyAdminMixin, TabularInline):
    model = WebhookEvent
    fk_name = "purchase"
    extra = 0
    fields = ["received_at", "event", "status", "deliveries", "processed_at", "note"]
    can_delete = False
    verbose_name_plural = "Razorpay webhooks for this purchase"


class MembershipStatusFilter(SimpleListFilter):
    title = "membership status"
    parameter_name = "membership"
    STATES = [
        ("active", "Active"), ("upcoming", "Starts later"), ("expired", "Expired"), ("cancelled", "Cancelled"),
        ("pending_payment", "Pending payment"), ("payment_failed", "Payment failed"),
        ("under_review", "Payment under review"),
    ]

    def lookups(self, request, model_admin):
        return self.STATES

    def queryset(self, request, queryset):
        if self.value() in dict(self.STATES):
            return queryset.filter(reporting.membership_q(self.value()))
        return queryset


@admin.register(Purchase)
class PurchaseAdmin(ReadOnlyAdminMixin, ModelAdmin):
    """Every online membership purchase: who bought what, the payment, and the membership it created."""

    AMOUNT_COLUMNS = ("base_display", "gst_display", "total_display")
    list_display = [
        "reference", "member_name", "matrimony_id", "billing_phone", "billing_email", "package_name",
        "base_display", "gst_display", "total_display", "currency", "provider", "status", "membership_status",
        "refund_status", "created_at", "paid_at", "membership_starts", "membership_ends",
    ]
    list_filter = [
        "package_code", "status", MembershipStatusFilter, "refund_status", "mode",
        ("created_at", DateFieldListFilter), ("paid_at", DateFieldListFilter),
        ("subscription__ends_at", DateFieldListFilter),
    ]
    list_select_related = ["user__profile", "subscription"]
    # No date_hierarchy: on MySQL/MariaDB it needs the server's time-zone tables, which XAMPP
    # doesn't install. The date filters below work everywhere.
    search_fields = [
        "reference", "razorpay_order_id", "razorpay_payment_id", "billing_name", "billing_email", "billing_phone",
        "user__first_name", "user__last_name", "user__email", "user__phone_number", "user__profile__display_name",
        "user__profile__profile_code",
    ]
    search_help_text = (
        "Search by name, Matrimony ID, mobile, email, purchase reference, or Razorpay order or payment id."
    )
    ordering = ["-created_at"]
    list_per_page = 50
    inlines = [RazorpayPaymentInline, PurchaseEventInline, WebhookEventInline]
    actions = ["check_with_razorpay", "export_csv"]
    extra_readonly = [
        "member_account", "member_profile", "provider", "membership_link", "membership_status", "membership_period",
        "refunded_display", "receipt_link", "service_case",
    ]

    # --- Permissions --------------------------------------------------------------

    def has_export_permission(self, request):
        return request.user.has_perm(EXPORT)

    def get_list_display(self, request):
        if request.user.has_perm(FINANCIALS):
            return self.list_display
        return [name for name in self.list_display if name not in self.AMOUNT_COLUMNS]

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            ("Member", {"fields": ["reference", "member_account", "member_profile", "billing_name", "billing_email",
                                   "billing_phone"]}),
            ("Plan when purchased", {"fields": [
                "package", "package_code", "package_name", "validity_months", "contact_view_limit", "tax_treatment",
            ]}),
            ("Amounts (snapshot when the order was created)", {"fields": [
                "base_amount", "gst_rate", "gst_amount", "total_amount", "amount_subunits", "currency",
            ]}),
            ("Payment", {"fields": [
                "provider", "mode", "status", "failure_reason", "razorpay_order_id", "razorpay_payment_id", "paid_at",
                "last_checked_at", "receipt_link",
            ]}),
            ("Refund (as reported by Razorpay)", {"fields": ["refund_status", "refunded_display", "refunded_at"]}),
            ("Membership", {"fields": ["membership_link", "membership_status", "membership_period"]}),
            ("Assisted matchmaking", {"fields": ["service_case"]}),
            ("Record", {"fields": ["created_at", "updated_at"]}),
        ]
        if not request.user.has_perm(FINANCIALS):
            fieldsets = [item for item in fieldsets if not item[0].startswith(("Amounts", "Refund"))]
        return fieldsets

    # --- Columns and fields ----------------------------------------------------------

    @admin.display(description="Member")
    def member_name(self, purchase):
        return purchase.billing_name or purchase.user.full_name or "—"

    @admin.display(description="Matrimony ID", ordering="user__profile__profile_code")
    def matrimony_id(self, purchase):
        profile = getattr(purchase.user, "profile", None)
        if profile is None:
            return "—"
        return format_html(
            '<a href="{}">{}</a>', reverse("admin:profiles_profile_change", args=[profile.pk]), profile.profile_code
        )

    @admin.display(description="Fee", ordering="base_amount")
    def base_display(self, purchase):
        return rupees(purchase.base_amount)

    @admin.display(description="GST", ordering="gst_amount")
    def gst_display(self, purchase):
        return rupees(purchase.gst_amount)

    @admin.display(description="Total", ordering="total_amount")
    def total_display(self, purchase):
        return rupees(purchase.total_amount)

    @admin.display(description="Provider")
    def provider(self, purchase):
        return "Razorpay" + (" (test)" if purchase.mode != "live" else "")

    @admin.display(description="Membership status")
    def membership_status(self, purchase):
        return reporting.membership_state(purchase)[1]

    @admin.display(description="Membership starts", ordering="subscription__starts_at")
    def membership_starts(self, purchase):
        return local(purchase.subscription.starts_at) if purchase.subscription else "—"

    @admin.display(description="Membership ends", ordering="subscription__ends_at")
    def membership_ends(self, purchase):
        return local(purchase.subscription.ends_at) if purchase.subscription else "—"

    @admin.display(description="Account")
    def member_account(self, purchase):
        return format_html('<a href="{}">{}</a>', reverse("admin:accounts_user_change", args=[purchase.user_id]),
                           purchase.user)

    @admin.display(description="Profile")
    def member_profile(self, purchase):
        profile = getattr(purchase.user, "profile", None)
        if profile is None:
            return "No profile"
        return format_html('<a href="{}">{} ({})</a>', reverse("admin:profiles_profile_change", args=[profile.pk]),
                           profile.display_name, profile.profile_code)

    @admin.display(description="Membership")
    def membership_link(self, purchase):
        if purchase.subscription is None:
            return "None: a membership is created only when the payment is verified."
        return format_html('<a href="{}">{}</a>',
                           reverse("admin:memberships_subscription_change", args=[purchase.subscription_id]),
                           purchase.subscription)

    @admin.display(description="Membership period")
    def membership_period(self, purchase):
        subscription = purchase.subscription
        if subscription is None:
            return "—"
        activated = f"activated {local(subscription.created_at)}"
        return f"{local(subscription.starts_at)} – {local(subscription.ends_at)} ({activated})"

    @admin.display(description="Refunded")
    def refunded_display(self, purchase):
        return rupees(purchase.refunded_amount_subunits / 100) if purchase.refunded_amount_subunits else "—"

    @admin.display(description="Receipt")
    def receipt_link(self, purchase):
        receipt = getattr(purchase, "receipt", None)
        if receipt is None:
            return "—"
        return format_html('<a href="{}">{}</a>', reverse("admin:payments_receipt_change", args=[receipt.pk]),
                           receipt.number)

    @admin.display(description="Service case")
    def service_case(self, purchase):
        from apps.memberships import assistance
        from apps.memberships.models import AssistanceKind, AssistanceRequest

        if purchase.subscription_id is None:
            return "—"
        case = (
            AssistanceRequest.objects.filter(subscription_id=purchase.subscription_id, kind=AssistanceKind.SERVICE)
            .select_related("assigned_to").first()
        )
        if case is None:
            return "Not an assisted package." if purchase.package_code not in assistance.SERVICE_CASE_PACKAGES else "—"
        if case.assigned_to is None:
            matchmaker = "not assigned"
        else:
            matchmaker = case.assigned_to.full_name or str(case.assigned_to)
        counts = (
            f"{case.follow_ups.count()} follow-ups, {case.exchanges.count()} contact exchanges, "
            f"{case.consultations.count()} consultations"
        )
        return format_html(
            '<a href="{}">{}</a>: {}, matchmaker {}. {}.',
            reverse("admin:memberships_assistancerequest_change", args=[case.pk]),
            case.get_kind_display(), case.get_status_display(), matchmaker, counts,
        )

    # --- Actions --------------------------------------------------------------------

    @admin.action(description="Check status with Razorpay (activates only confirmed captured payments)", permissions=["change"])
    def check_with_razorpay(self, request, queryset):
        checked = 0
        for purchase in queryset.exclude(razorpay_order_id=None):
            try:
                services.reconcile(purchase, EventSource.STAFF_CHECK, request.user)
                checked += 1
            except RazorpayError as exc:
                self.message_user(request, f"{purchase.reference}: {exc}", messages.ERROR)
        if checked:
            self.message_user(request, f"Checked {checked} purchase(s) with Razorpay.", messages.SUCCESS)

    @admin.action(description="Export selected purchases to CSV", permissions=["export"])
    def export_csv(self, request, queryset):
        """Business fields only: no mobile numbers, emails, signatures or secrets. Cells can't run as formulas."""
        financials = request.user.has_perm(FINANCIALS)
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="membership-purchases-{timezone.localdate():%Y%m%d}.csv"'
        response["Cache-Control"] = "private, no-store"
        writer = csv.writer(response)
        header = ["Reference", "Member", "Matrimony ID", "Plan", "Payment status", "Membership status", "Refund status",
                  "Currency", "Razorpay order", "Razorpay payment", "Mode", "Ordered", "Paid", "Membership starts",
                  "Membership ends"]
        if financials:
            header[7:7] = ["Fee", "GST rate %", "GST", "Total", "Refunded"]
        writer.writerow(header)
        rows = queryset.select_related("user__profile", "subscription").order_by("-created_at")
        for purchase in rows.iterator(chunk_size=500):
            profile = getattr(purchase.user, "profile", None)
            row = [
                purchase.reference, self.member_name(purchase), profile.profile_code if profile else "",
                purchase.package_name, purchase.get_status_display(), reporting.membership_state(purchase)[1],
                purchase.get_refund_status_display(), purchase.currency, purchase.razorpay_order_id or "",
                purchase.razorpay_payment_id or "", purchase.mode, local(purchase.created_at), local(purchase.paid_at),
                self.membership_starts(purchase), self.membership_ends(purchase),
            ]
            if financials:
                row[7:7] = [purchase.base_amount, purchase.gst_rate, purchase.gst_amount, purchase.total_amount,
                            f"{purchase.refunded_amount_subunits / 100:.2f}"]
            writer.writerow([safe_cell(value) for value in row])
        # Who exported how many rows, for audit; no personal data in the log.
        logger.info("Staff user %s exported %s membership purchases to CSV", request.user.pk, queryset.count())
        return response

    # --- Summary ------------------------------------------------------------------------

    def get_urls(self):
        return [
            path("summary/", self.admin_site.admin_view(self.summary_view), name="payments_purchase_summary"),
            *super().get_urls(),
        ]

    def summary_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        figures = reporting.summary()
        packages = [{**row, "gross_display": rupees(row["gross"])} for row in reporting.by_package()]
        context = {
            **self.admin_site.each_context(request),
            "title": "Membership purchases summary",
            "opts": self.model._meta,
            "figures": figures,
            "money": {key: rupees(figures[key]) for key in ("gross", "gst", "refunded_amount", "net", "gross_month",
                                                             "test_gross")},
            "packages": packages,
            "financials": request.user.has_perm(FINANCIALS),
            "changelist": reverse("admin:payments_purchase_changelist"),
            "month": reporting.month_start(),
        }
        return TemplateResponse(request, "admin/payments/purchase/summary.html", context)


def safe_cell(value):
    """Spreadsheet formula injection guard: text starting with = + - @ or a control character is quoted."""
    if isinstance(value, datetime):
        value = local(value)
    text = "" if value is None else str(value)
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@admin.register(Receipt)
class ReceiptAdmin(ReadOnlyAdminMixin, ModelAdmin):
    list_display = ["number", "purchase", "issued_at", "email_status", "email_attempts", "email_sent_at"]
    list_filter = ["email_status"]
    search_fields = ["number", "purchase__reference", "purchase__billing_email"]
    ordering = ["-issued_at"]
    actions = ["resend_email"]

    @admin.action(description="Send the receipt email again", permissions=["change"])
    def resend_email(self, request, queryset):
        sent = 0
        for receipt in queryset.select_related("purchase"):
            if send_receipt_email(receipt, force=True):
                sent += 1
            else:
                self.message_user(request, f"{receipt.number}: not sent. See the last error on the receipt.", messages.ERROR)
        if sent:
            self.message_user(request, f"{sent} receipt email(s) accepted by the mail server.", messages.SUCCESS)


@admin.register(WebhookEvent)
class WebhookEventAdmin(ReadOnlyAdminMixin, ModelAdmin):
    list_display = ["event", "event_id", "status", "purchase", "deliveries", "received_at", "processed_at"]
    list_filter = ["status", "event"]
    search_fields = ["event_id", "razorpay_order_id", "purchase__reference"]
    ordering = ["-received_at"]
