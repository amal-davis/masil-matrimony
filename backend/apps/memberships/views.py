from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsMember

from .models import Subscription


def subscription_data(subscription: Subscription) -> dict:
    plan = subscription.plan
    return {
        "id": str(subscription.public_id),
        "plan_code": plan.code,
        "plan_name": plan.name,
        "status": subscription.display_status,
        "starts_at": subscription.starts_at,
        "ends_at": subscription.ends_at,
        "validity_months": plan.validity_months,
        "contact_view_limit": plan.contact_view_limit,
        "contact_views_used": subscription.contact_views_used if plan.contact_view_limit else None,
    }


def current_subscription(user):
    return Subscription.objects.current().filter(user=user).order_by("-ends_at").first()


class MyMembershipView(APIView):
    """The member's current membership and their subscription history."""

    permission_classes = [IsMember]

    @extend_schema(tags=["memberships"])
    def get(self, request):
        current = current_subscription(request.user)
        history = Subscription.objects.filter(user=request.user).order_by("-created_at")
        return Response(
            {
                "current": subscription_data(current) if current else None,
                "history": [subscription_data(item) for item in history],
                # No payment gateway is integrated (apps.payments is a placeholder), so purchases are
                # handled offline and activated by staff. Deliberately not a setting: it may only become
                # true once server-verified payments exist.
                "online_payment_available": False,
            }
        )
