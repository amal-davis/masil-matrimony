from django.contrib import admin
from django.contrib.admin import helpers
from django.db import transaction
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from apps.notifications.models import NotificationKind
from apps.notifications.services import notify

from .models import MembershipPackage, Subscription, SubscriptionStatus


def rupees(value) -> str:
    return "—" if value is None else f"₹{value:,.2f}"


@admin.register(MembershipPackage)
class MembershipPackageAdmin(ModelAdmin):
    """
    The six packages. The set is fixed (entitlement rules key off the codes), so
    packages can't be added or deleted here. Staff with change permission edit the
    copy and availability; fees, tax, validity and limits need the separate
    "Can change package terms" permission, which only superusers have by default.
    Edits apply to subscriptions recorded afterwards: existing subscriptions keep
    the fee, validity and contact limit they were recorded with.
    """

    list_display = [
        "name", "code", "category", "fee_display", "tax_treatment", "validity_display",
        "contact_view_limit", "outgoing_interest_limit", "is_available", "display_order",
    ]
    list_filter = ["category", "is_available", "tax_treatment"]
    search_fields = ["name", "code"]
    ordering = ["display_order", "pk"]
    fieldsets = [
        (None, {"fields": ["code", "category", "is_available", "display_order"]}),
        ("Fees and tax", {
            "fields": ["fee", "fee_label", "tax_treatment", "stated_gst_rate", "gst_display", "total_display"],
        }),
        ("Validity and limits", {"fields": ["validity_months", "contact_view_limit", "outgoing_interest_limit"]}),
        ("Website copy", {"fields": [
            "name", "subtitle", "tagline", "service_label", "description", "benefits", "terms_title", "terms_body",
            "cta_label",
        ]}),
        ("Record", {"fields": ["created_at", "updated_at"]}),
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        fields = ["code", "gst_display", "total_display", "created_at", "updated_at"]
        if not request.user.has_perm("memberships.change_package_terms"):
            fields += list(MembershipPackage.COMMERCIAL_FIELDS)
        return fields

    @admin.display(description="Fee (excl. GST)", ordering="fee")
    def fee_display(self, package):
        return rupees(package.fee)

    @admin.display(description="Validity")
    def validity_display(self, package):
        return f"{package.validity_months} months" if package.validity_months else "No expiry"

    @admin.display(description="GST amount")
    def gst_display(self, package):
        return rupees(package.gst_amount) if package.gst_amount is not None else "Applicable GST, added at payment"

    @admin.display(description="Total payable")
    def total_display(self, package):
        total = package.total_payable
        return rupees(total) if total is not None else "Fee plus applicable GST (no GST rate is configured)"


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    """
    Staff record a subscription after confirming an offline payment, then use
    "Activate" to start its validity period. There is no online checkout or
    payment gateway yet, so there are no payment records to show here.
    """

    list_display = ["user", "matrimony_id", "plan_code", "status", "starts_at", "ends_at", "created_at"]
    list_filter = ["plan_code", "status"]
    list_select_related = ["user__profile"]
    search_fields = ["user__email", "user__phone_number", "user__profile__profile_code"]
    search_help_text = "Search by email, mobile number or Matrimony ID."
    ordering = ["-created_at"]
    list_per_page = 50
    autocomplete_fields = ["user"]
    # Status changes only through the actions below, so the validity period and
    # the member's notification are always set correctly. The package terms are
    # copied from the package when the subscription is recorded, and contact views
    # are counted by the contact-access API, so staff can't edit either.
    readonly_fields = [
        "public_id", "status", "starts_at", "ends_at", "package_fee", "validity_months", "contact_view_limit",
        "contact_views_used", "activated_by", "created_at", "updated_at",
    ]
    fieldsets = [
        (None, {"fields": ["public_id", "user", "plan_code", "status"]}),
        ("Terms when recorded", {"fields": ["package_fee", "validity_months", "contact_view_limit"]}),
        ("Validity", {"fields": ["starts_at", "ends_at", "contact_views_used"]}),
        ("Staff", {"fields": ["staff_note", "activated_by", "created_at", "updated_at"]}),
    ]
    actions = ["activate", "cancel"]

    def get_readonly_fields(self, request, obj=None):
        # The package can't change after recording: its terms were copied then.
        return [*self.readonly_fields, "user", "plan_code"] if obj else self.readonly_fields

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "plan_code":
            available = set(MembershipPackage.objects.available().values_list("code", flat=True))
            kwargs["choices"] = [("", "---------")] + [c for c in db_field.choices if c[0] in available]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    @admin.display(description="Matrimony ID", ordering="user__profile__profile_code")
    def matrimony_id(self, subscription):
        profile = getattr(subscription.user, "profile", None)
        if profile is None:
            return "—"
        return format_html(
            '<a href="{}">{}</a>', reverse("admin:profiles_profile_change", args=[profile.pk]), profile.profile_code
        )

    @admin.action(description="Cancel selected subscriptions", permissions=["change"])
    def cancel(self, request, queryset):
        to_cancel = list(queryset.exclude(status=SubscriptionStatus.CANCELLED).select_related("user"))
        if not to_cancel:
            self.message_user(request, "The selected subscriptions are already cancelled.")
            return None
        # Cancelling ends a member's benefits, so ask first.
        if request.POST.get("confirmed") != "yes":
            return TemplateResponse(
                request,
                "admin/memberships/subscription/cancel_confirmation.html",
                {
                    **self.admin_site.each_context(request),
                    "title": "Cancel subscriptions",
                    "opts": self.model._meta,
                    "subscriptions": to_cancel,
                    "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                },
            )
        with transaction.atomic():
            for subscription in to_cancel:
                subscription.status = SubscriptionStatus.CANCELLED
                subscription.save(update_fields=["status", "updated_at"])
                self.log_change(request, subscription, "Cancelled from the subscription list.")
        self.message_user(request, f"Cancelled {len(to_cancel)} subscription(s).")
        return None

    @admin.action(description="Activate selected subscriptions (payment confirmed)", permissions=["change"])
    def activate(self, request, queryset):
        count = 0
        with transaction.atomic():
            for subscription in queryset.select_for_update().filter(status=SubscriptionStatus.PENDING):
                subscription.activate(by=request.user)
                subscription.save()
                notify(
                    subscription.user,
                    NotificationKind.MEMBERSHIP_ACTIVATED,
                    f"Your {subscription.plan.name} is active",
                    f"Valid until {subscription.ends_at:%d %b %Y}.",
                    "/dashboard/membership",
                )
                self.log_change(request, subscription, "Activated after payment was confirmed.")
                count += 1
        self.message_user(request, f"Activated {count} subscription(s). Only pending subscriptions are changed.")
