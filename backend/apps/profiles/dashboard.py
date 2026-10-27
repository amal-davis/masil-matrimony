"""GET /dashboard/summary/: everything the member's dashboard overview shows, in one request."""
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response

from apps.interactions.models import Interest, InterestStatus, Shortlist
from apps.interactions.views import interest_data
from apps.interactions import messaging, profile_views
from apps.memberships.views import current_subscription, entitlements_data, subscription_data
from apps.notifications.models import Notification
from apps.notifications.views import notification_data

from . import services
from .models import Profile
from .photos import signed_photo_url
from .views import MemberAPIView

RECENT = 5


def interest_counts(profile: Profile) -> dict:
    received = Interest.objects.filter(receiver=profile).exclude(status=InterestStatus.WITHDRAWN).aggregate(
        total=Count("pk"),
        pending=Count("pk", filter=Q(status=InterestStatus.PENDING)),
        accepted=Count("pk", filter=Q(status=InterestStatus.ACCEPTED)),
    )
    sent = Interest.objects.filter(sender=profile).exclude(status=InterestStatus.WITHDRAWN).aggregate(
        total=Count("pk"),
        pending=Count("pk", filter=Q(status=InterestStatus.PENDING)),
        accepted=Count("pk", filter=Q(status=InterestStatus.ACCEPTED)),
    )
    return {
        "received": received["total"],
        # Interests waiting for this member to accept or decline.
        "awaiting_your_response": received["pending"],
        "sent": sent["total"],
        "sent_pending": sent["pending"],
        "accepted": received["accepted"] + sent["accepted"],
    }


class DashboardSummaryView(MemberAPIView):
    @extend_schema(tags=["dashboard"])
    def get(self, request):
        user = request.user
        profile = Profile.objects.select_related("partner_preference").filter(user=user).first()
        subscription = current_subscription(user)
        notifications = Notification.objects.filter(recipient=user)

        data = {
            "member": {"first_name": user.first_name, "phone_verified": user.phone_verified_at is not None},
            "membership": subscription_data(subscription) if subscription else None,
            # What the membership allows now (memberships.entitlements): the dashboard shows these, never its own guess.
            "entitlements": entitlements_data(user),
            "notifications": {
                "unread": notifications.filter(read_at=None).count(),
                "recent": [notification_data(item) for item in notifications[:RECENT]],
            },
            "profile": None,
            "interests": None,
            "shortlisted": 0,
            "unread_messages": 0,
            "profile_viewers": 0,
            "verification": None,
            "recent_interests": [],
        }
        if profile is None:
            return Response(data)

        photo = profile.photos.filter(is_primary=True).first()
        data["profile"] = {
            "profile_code": profile.profile_code,
            "display_name": profile.display_name,
            "status": profile.status,
            "review_note": profile.review_note,
            "completion": services.completion(profile),
            "missing_for_review": services.missing_for_review(profile),
            "photo": (
                {"url": signed_photo_url(photo, request), "status": photo.status} if photo else None
            ),
            "photo_count": profile.photos.count(),
        }
        data["interests"] = interest_counts(profile)
        data["shortlisted"] = Shortlist.objects.filter(owner=profile).count()
        data["unread_messages"] = messaging.unread_count(profile)
        # The number only; who they are needs Feature.PROFILE_VIEWERS (GET /profile-views/).
        data["profile_viewers"] = profile_views.viewer_count(profile)
        data["verification"] = {
            "status": profile.verification_status,
            "note": profile.verification_note,
            "verified_at": profile.verified_at,
        }

        recent = (
            Interest.objects.filter(Q(receiver=profile) | Q(sender=profile))
            .exclude(status=InterestStatus.WITHDRAWN)
            .select_related("sender__user", "receiver__user")
            .order_by("-updated_at")[:RECENT]
        )
        data["recent_interests"] = [
            {
                **interest_data(profile, item, item.receiver if item.sender_id == profile.pk else item.sender, request),
                "direction": "sent" if item.sender_id == profile.pk else "received",
            }
            for item in recent
        ]
        return Response(data)
