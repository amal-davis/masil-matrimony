"""
Membership checkout API. Every member endpoint works only on the signed-in
member's own purchases and receipts: lookups are always filtered by
request.user, so changing an id in the URL finds nothing (404).
"""
import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsMember
from apps.memberships.plans import PackageCode

from . import services, webhooks
from .models import Purchase, PurchaseStatus, Receipt
from .razorpay_api import RazorpayError
from .receipts import receipt_data

logger = logging.getLogger(__name__)


def money(value) -> str | None:
    return None if value is None else f"{value:.2f}"


def error_response(error: services.CheckoutError) -> Response:
    return Response({"detail": error.message, "code": error.code}, status=error.status)


PAYABLE = (PurchaseStatus.AWAITING_PAYMENT, PurchaseStatus.FAILED)
CHECKABLE = (PurchaseStatus.AWAITING_PAYMENT, PurchaseStatus.AUTHORIZED, PurchaseStatus.FAILED)


def purchase_data(purchase: Purchase) -> dict:
    receipt = getattr(purchase, "receipt", None)
    subscription = purchase.subscription
    return {
        "reference": purchase.reference,
        "status": purchase.status,
        "status_label": purchase.get_status_display(),
        "package_code": purchase.package_code,
        "package_name": purchase.package_name,
        "validity_months": purchase.validity_months,
        "amounts": {
            "base": money(purchase.base_amount),
            "gst_rate": money(purchase.gst_rate),
            "gst": money(purchase.gst_amount),
            "total": money(purchase.total_amount),
            "currency": purchase.currency,
        },
        "created_at": purchase.created_at,
        "paid_at": purchase.paid_at,
        "failure_reason": purchase.failure_reason,
        "razorpay_order_id": purchase.razorpay_order_id,
        "razorpay_payment_id": purchase.razorpay_payment_id,
        "membership": (
            {"starts_at": subscription.starts_at, "ends_at": subscription.ends_at} if subscription else None
        ),
        "receipt": {"id": str(receipt.public_id), "number": receipt.number} if receipt else None,
        # The member can reopen Razorpay Checkout for this order (e.g. after closing it or a failed attempt).
        "can_pay": purchase.status in PAYABLE and bool(purchase.razorpay_order_id),
        "can_check_status": purchase.status in CHECKABLE and bool(purchase.razorpay_order_id),
        "test_mode": purchase.mode == "test",
    }


def own_purchase(request, reference: str) -> Purchase:
    purchase = (
        Purchase.objects.select_related("subscription", "receipt")
        .filter(user=request.user, reference=reference)
        .first()
    )
    if purchase is None:
        raise NotFound("Purchase not found.")
    return purchase


class CheckoutQuoteView(APIView):
    """
    What buying a package would cost and whether the member can buy it now.
    Prices come from the package; `blocked` says why checkout isn't possible.
    """

    permission_classes = [IsMember]

    @extend_schema(tags=["payments"])
    def get(self, request, package_code):
        try:
            package = services.purchasable_package(package_code)
        except services.CheckoutError as error:
            return error_response(error)
        price, blocked = None, None
        try:
            price = services.quote(package)
            services.check_checkout(request.user, package)
        except services.CheckoutError as error:
            blocked = {"code": error.code, "message": error.message}
        user = request.user
        return Response(
            {
                "package": {
                    "code": package.code,
                    "name": package.name,
                    "description": package.description,
                    "validity_months": package.validity_months,
                    "fee_label": package.fee_label,
                    "terms": {"title": package.terms_title, "body": package.terms_body},
                },
                "price": (
                    {
                        "base": money(price.base),
                        "gst_rate": money(price.gst_rate),
                        "gst": money(price.gst),
                        "total": money(price.total),
                        "currency": price.currency,
                    }
                    if price
                    else None
                ),
                # Receipts go to the registered details; the browser can't choose another address.
                "customer": {"name": user.full_name, "email": user.email, "phone": user.phone_number},
                "available": blocked is None,
                "blocked": blocked,
                # Only claim test mode when test keys are actually configured.
                "test_mode": services.razorpay_api.configured() and settings.RAZORPAY_MODE == "test",
            }
        )


class StartPurchaseSerializer(serializers.Serializer):
    package = serializers.ChoiceField(choices=[code for code in PackageCode.values])


class PurchaseListView(APIView):
    """GET: the member's purchases, newest first. POST {"package": code}: start (or resume) a checkout."""

    permission_classes = [IsMember]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "payments"
        return super().get_throttles()

    @extend_schema(tags=["payments"])
    def get(self, request):
        from rest_framework.settings import api_settings

        paginator = api_settings.DEFAULT_PAGINATION_CLASS()
        queryset = Purchase.objects.filter(user=request.user).select_related("subscription", "receipt")
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([purchase_data(item) for item in page])

    @extend_schema(request=StartPurchaseSerializer, tags=["payments"])
    def post(self, request):
        serializer = StartPurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Choose a valid package.", "code": "invalid_package", **serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            purchase = services.start_checkout(request.user, serializer.validated_data["package"])
        except services.CheckoutError as error:
            return error_response(error)
        return Response(
            {"purchase": purchase_data(purchase), "checkout": services.checkout_options(purchase)},
            status=status.HTTP_201_CREATED,
        )


class PurchaseDetailView(APIView):
    permission_classes = [IsMember]

    @extend_schema(tags=["payments"])
    def get(self, request, reference):
        purchase = own_purchase(request, reference)
        data = purchase_data(purchase)
        if data["can_pay"]:
            data["checkout"] = services.checkout_options(purchase)
        return Response(data)


class VerifySerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField(max_length=40)
    razorpay_payment_id = serializers.CharField(max_length=40)
    razorpay_signature = serializers.RegexField(r"^[0-9a-fA-F]{64}$")


class VerifyPaymentView(APIView):
    """
    Razorpay Checkout's success callback. Activates nothing by itself: the
    signature is checked, then Razorpay's API is asked whether the payment was captured.
    """

    permission_classes = [IsMember]
    throttle_scope = "payments"

    @extend_schema(request=VerifySerializer, tags=["payments"])
    def post(self, request, reference):
        purchase = own_purchase(request, reference)
        serializer = VerifySerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(services.InvalidCallback())
        data = serializer.validated_data
        try:
            purchase = services.verify_checkout(
                purchase, data["razorpay_order_id"], data["razorpay_payment_id"], data["razorpay_signature"]
            )
        except services.CheckoutError as error:
            return error_response(error)
        except RazorpayError as exc:
            logger.error("Purchase %s: couldn't confirm with Razorpay: %s", purchase.reference, exc)
            return Response(
                {**purchase_data(purchase), "confirmation_pending": True}, status=status.HTTP_202_ACCEPTED
            )
        return Response(purchase_data(own_purchase(request, reference)))


class RefreshPaymentView(APIView):
    """Ask Razorpay for the current state of the purchase's order ("Check payment status")."""

    permission_classes = [IsMember]
    throttle_scope = "payments"

    @extend_schema(tags=["payments"])
    def post(self, request, reference):
        purchase = own_purchase(request, reference)
        if purchase.status in CHECKABLE and purchase.razorpay_order_id:
            try:
                services.reconcile(purchase)
            except RazorpayError as exc:
                logger.error("Purchase %s: status check failed: %s", purchase.reference, exc)
                return Response(
                    {"detail": "We couldn't reach the payment provider. Please try again in a minute.",
                     "code": "provider_unreachable"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        return Response(purchase_data(own_purchase(request, reference)))


class ReceiptView(APIView):
    """A receipt of one of the member's own paid purchases."""

    permission_classes = [IsMember]

    @extend_schema(tags=["payments"])
    def get(self, request, receipt_id):
        receipt = (
            Receipt.objects.select_related("purchase__subscription")
            .filter(public_id=receipt_id, purchase__user=request.user)
            .first()
        )
        if receipt is None:
            raise NotFound("Receipt not found.")
        return Response(receipt_data(receipt))


@method_decorator(csrf_exempt, name="dispatch")
class RazorpayWebhookView(View):
    """Razorpay's server calls this; authenticity comes only from the signature (apps.payments.webhooks)."""

    http_method_names = ["post"]

    def post(self, request):
        code, note = webhooks.handle(
            request.body,
            request.headers.get("X-Razorpay-Signature", ""),
            request.headers.get("X-Razorpay-Event-Id", ""),
        )
        return JsonResponse({"detail": note}, status=code)
