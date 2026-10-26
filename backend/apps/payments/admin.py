"""
Payments in the admin are records, not switches: nothing here marks a purchase
paid. The only way to "paid" is apps.payments.services.reconcile, which asks
Razorpay. Staff can trigger that check ("Check status with Razorpay"), resend
receipt emails, and read webhook history.
"""
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from . import services
from .models import Purchase, RazorpayPayment, Receipt, WebhookEvent
from .razorpay_api import RazorpayError
from .receipts import send_receipt_email


class ReadOnlyAdminMixin:
    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        # Change permission is kept (the actions need it), but no field can be edited.
        return [field.name for field in self.model._meta.fields]


class RazorpayPaymentInline(ReadOnlyAdminMixin, TabularInline):
    model = RazorpayPayment
    extra = 0
    fields = ["payment_id", "status", "amount_subunits", "currency", "method", "error_description", "razorpay_created_at"]
    can_delete = False


@admin.register(Purchase)
class PurchaseAdmin(ReadOnlyAdminMixin, ModelAdmin):
    list_display = ["reference", "matrimony_id", "package_name", "total_display", "status", "mode", "created_at", "paid_at"]
    list_filter = ["status", "mode", "package_code"]
    list_select_related = ["user__profile"]
    search_fields = [
        "reference", "razorpay_order_id", "razorpay_payment_id", "billing_email", "user__phone_number",
        "user__profile__profile_code",
    ]
    search_help_text = "Search by purchase reference, Razorpay order or payment id, email, mobile or Matrimony ID."
    ordering = ["-created_at"]
    list_per_page = 50
    inlines = [RazorpayPaymentInline]
    actions = ["check_with_razorpay"]
    fieldsets = [
        (None, {"fields": ["reference", "user", "status", "mode", "failure_reason"]}),
        ("What was sold", {"fields": [
            "package", "package_code", "package_name", "validity_months", "contact_view_limit", "tax_treatment",
        ]}),
        ("Amounts", {"fields": ["base_amount", "gst_rate", "gst_amount", "total_amount", "amount_subunits", "currency"]}),
        ("Billing contact", {"fields": ["billing_name", "billing_email", "billing_phone"]}),
        ("Razorpay", {"fields": ["razorpay_order_id", "razorpay_payment_id", "paid_at", "last_checked_at"]}),
        ("Membership", {"fields": ["subscription", "created_at", "updated_at"]}),
    ]

    @admin.display(description="Total", ordering="total_amount")
    def total_display(self, purchase):
        return f"₹{purchase.total_amount:,.2f}"

    @admin.display(description="Matrimony ID", ordering="user__profile__profile_code")
    def matrimony_id(self, purchase):
        profile = getattr(purchase.user, "profile", None)
        if profile is None:
            return "—"
        return format_html(
            '<a href="{}">{}</a>', reverse("admin:profiles_profile_change", args=[profile.pk]), profile.profile_code
        )

    @admin.action(description="Check status with Razorpay (activates only confirmed captured payments)", permissions=["change"])
    def check_with_razorpay(self, request, queryset):
        checked = failed = 0
        for purchase in queryset.exclude(razorpay_order_id=None):
            try:
                services.reconcile(purchase)
                checked += 1
            except RazorpayError as exc:
                failed += 1
                self.message_user(request, f"{purchase.reference}: {exc}", messages.ERROR)
        if checked:
            self.message_user(request, f"Checked {checked} purchase(s) with Razorpay.", messages.SUCCESS)


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

