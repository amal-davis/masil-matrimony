import logging

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import EnquiryCreateSerializer

logger = logging.getLogger(__name__)

# The largest valid submission is about 3 KB of JSON; anything far bigger is not a contact form.
MAX_REQUEST_BYTES = 16 * 1024


class EnquiryCreateView(APIView):
    """
    Public contact form. Stores the enquiry for staff to follow up in the admin.
    No authentication, so no session or CSRF is involved; abuse is limited by the
    "enquiries" throttle scope, a request size cap and a honeypot field.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "enquiries"

    @extend_schema(request=EnquiryCreateSerializer, responses={201: EnquiryCreateSerializer}, tags=["enquiries"])
    def post(self, request):
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        if length > MAX_REQUEST_BYTES:
            return Response(
                {"detail": "The request is too large."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        serializer = EnquiryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.is_spam():
            # Answer like a success so bots don't learn to skip the trap; nothing is stored.
            logger.info("Enquiry discarded: honeypot field was filled in")
            return Response({"id": None}, status=status.HTTP_201_CREATED)

        enquiry = serializer.save()
        # Log the id only, never the visitor's details or message.
        logger.info("Enquiry %s received", enquiry.public_id)
        return Response({"id": str(enquiry.public_id)}, status=status.HTTP_201_CREATED)
