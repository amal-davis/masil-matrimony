from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.profiles.views import MemberAPIView, paginated

from .models import Notification


def notification_data(item: Notification) -> dict:
    return {
        "id": str(item.public_id),
        "kind": item.kind,
        "title": item.title,
        "body": item.body,
        "link": item.link,
        "created_at": item.created_at,
        "read": item.read_at is not None,
    }


class NotificationListView(MemberAPIView):
    @extend_schema(tags=["notifications"])
    def get(self, request):
        queryset = Notification.objects.filter(recipient=request.user)
        if request.query_params.get("unread") in ("1", "true"):
            queryset = queryset.filter(read_at=None)
        response = paginated(self, queryset, notification_data)
        response.data["unread_count"] = Notification.objects.filter(recipient=request.user, read_at=None).count()
        return response


class NotificationReadView(MemberAPIView):
    @extend_schema(request=None, responses={204: None}, tags=["notifications"])
    def post(self, request, notification_id):
        updated = Notification.objects.filter(
            recipient=request.user, public_id=notification_id, read_at=None
        ).update(read_at=timezone.now())
        if not updated and not Notification.objects.filter(recipient=request.user, public_id=notification_id).exists():
            raise NotFound("Notification not found.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationReadAllView(MemberAPIView):
    @extend_schema(request=None, responses={204: None}, tags=["notifications"])
    def post(self, request):
        Notification.objects.filter(recipient=request.user, read_at=None).update(read_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)
