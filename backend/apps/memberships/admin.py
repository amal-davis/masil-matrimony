from django.contrib import admin
from django.db import transaction

from apps.notifications.models import NotificationKind
from apps.notifications.services import notify

from .models import Subscription, SubscriptionStatus


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """
    Staff record a subscription after confirming an offline payment, then use
    "Activate" to start its validity period. There is no online checkout.
    """

    list_display = ["user", "plan_code", "status", "starts_at", "ends_at", "created_at"]
    list_filter = ["plan_code", "status"]
    search_fields = ["user__email", "user__phone_number"]
    autocomplete_fields = ["user"]
    # Status changes only through the actions below, so the validity period and
    # the member's notification are always set correctly.
    readonly_fields = ["public_id", "status", "starts_at", "ends_at", "activated_by", "created_at", "updated_at"]
    fields = ["public_id", "user", "plan_code", "status", "starts_at", "ends_at", "contact_views_used",
              "staff_note", "activated_by", "created_at", "updated_at"]
    actions = ["activate", "cancel"]

    @admin.action(description="Cancel selected subscriptions")
    def cancel(self, request, queryset):
        count = queryset.exclude(status=SubscriptionStatus.CANCELLED).update(status=SubscriptionStatus.CANCELLED)
        self.message_user(request, f"Cancelled {count} subscription(s).")

    @admin.action(description="Activate selected subscriptions (payment confirmed)")
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
                count += 1
        self.message_user(request, f"Activated {count} subscription(s). Only pending subscriptions are changed.")
