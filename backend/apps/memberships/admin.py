from django.contrib import admin
from django.contrib.admin import helpers
from django.db import transaction
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from apps.notifications.models import NotificationKind
from apps.notifications.services import notify

from .models import Subscription, SubscriptionStatus


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
    # the member's notification are always set correctly.
    readonly_fields = ["public_id", "status", "starts_at", "ends_at", "activated_by", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["public_id", "user", "plan_code", "status"]}),
        ("Validity", {"fields": ["starts_at", "ends_at", "contact_views_used"]}),
        ("Staff", {"fields": ["staff_note", "activated_by", "created_at", "updated_at"]}),
    ]
    actions = ["activate", "cancel"]

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
