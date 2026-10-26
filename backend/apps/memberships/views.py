from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsMember
from apps.interactions.services import free_interests_used
from apps.payments import razorpay_api

from .entitlements import current_subscription, entitlements_for
from .models import MembershipPackage, Subscription


def money(value) -> str | None:
    """Rupee amounts as decimal strings ("12000.00"), so no precision is lost."""
    return None if value is None else f"{value:.2f}"


def package_data(package: MembershipPackage) -> dict:
    return {
        "code": package.code,
        "category": package.category,
        "name": package.name,
        "subtitle": package.subtitle,
        "tagline": package.tagline,
        "service_label": package.service_label,
        "description": package.description,
        "fee": money(package.fee),
        "fee_label": package.fee_label,
        "tax_treatment": package.tax_treatment,
        "stated_gst_rate": money(package.stated_gst_rate),
        # The rate the total uses (stated, or the configured applicable rate); None while unconfirmed.
        "gst_rate": money(package.gst_rate),
        "gst_amount": money(package.gst_amount),
        # None while it depends on an applicable GST rate that isn't configured (MEMBERSHIP_GST_RATE_PERCENT).
        "total_payable": money(package.total_payable),
        "validity_months": package.validity_months,
        "contact_view_limit": package.contact_view_limit,
        "outgoing_interest_limit": package.outgoing_interest_limit,
        "benefits": [{"title": item["title"], "detail": item.get("detail", "")} for item in package.benefits],
        "terms": {"title": package.terms_title, "body": package.terms_body},
        "cta_label": package.cta_label,
    }


class PackageListView(APIView):
    """The packages offered on the website, in display order. Public."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["memberships"])
    def get(self, request):
        return Response([package_data(item) for item in MembershipPackage.objects.available()])


def subscription_data(subscription: Subscription) -> dict:
    plan = subscription.plan
    return {
        "id": str(subscription.public_id),
        "plan_code": plan.code,
        "plan_name": plan.name,
        "status": subscription.display_status,
        "starts_at": subscription.starts_at,
        "ends_at": subscription.ends_at,
        "validity_months": subscription.validity_months,
        "package_fee": money(subscription.package_fee),
        "contact_view_limit": subscription.contact_view_limit,
        "contact_views_used": subscription.contact_views_used if subscription.contact_view_limit else None,
    }


class MyMembershipView(APIView):
    """The member's current membership, what it allows, and their subscription history."""

    permission_classes = [IsMember]

    @extend_schema(tags=["memberships"])
    def get(self, request):
        current = current_subscription(request.user)
        history = Subscription.objects.filter(user=request.user).order_by("-created_at")
        entitlements = entitlements_for(request.user)
        limit = entitlements.outgoing_interest_limit
        counted = entitlements.is_free and limit is not None
        return Response(
            {
                "current": subscription_data(current) if current else None,
                "history": [subscription_data(item) for item in history],
                "entitlements": {
                    "package_code": entitlements.package.code,
                    "outgoing_interest_limit": limit,
                    "outgoing_interests_used": (
                        free_interests_used(getattr(request.user, "profile", None)) if counted else None
                    ),
                    "contact_view_limit": entitlements.contact_view_limit,
                },
                # Razorpay checkout is configured (apps.payments). Whether a given package can be
                # bought is decided per package by GET /payments/checkout/<code>/.
                "online_payment_available": razorpay_api.configured(),
            }
        )
