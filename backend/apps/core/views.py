import logging

from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

_health_response = inline_serializer(
    name="HealthResponse",
    fields={
        "status": serializers.CharField(),
        "service": serializers.CharField(),
        "api_version": serializers.CharField(),
    },
)


class HealthView(APIView):
    """Liveness check: the API process is up and serving requests."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(responses={200: _health_response}, tags=["system"])
    def get(self, request):
        return Response(
            {"status": "ok", "service": "matrimony-api", "api_version": "v1"}
        )


class ReadinessView(APIView):
    """Readiness check: the API can reach its database."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    @extend_schema(responses={200: _health_response, 503: _health_response}, tags=["system"])
    def get(self, request):
        body = {"service": "matrimony-api", "api_version": "v1"}
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            # Log details server-side only; never return them to the client.
            logger.exception("Readiness check failed: database unavailable")
            return Response(
                {"status": "unavailable", **body},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"status": "ok", **body})
