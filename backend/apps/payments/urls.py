from django.urls import path

from .views import (
    CheckoutQuoteView,
    PurchaseDetailView,
    PurchaseListView,
    RazorpayWebhookView,
    ReceiptView,
    RefreshPaymentView,
    VerifyPaymentView,
)

app_name = "payments"

urlpatterns = [
    path("checkout/<str:package_code>/", CheckoutQuoteView.as_view(), name="checkout-quote"),
    path("purchases/", PurchaseListView.as_view(), name="purchases"),
    path("purchases/<str:reference>/", PurchaseDetailView.as_view(), name="purchase"),
    path("purchases/<str:reference>/verify/", VerifyPaymentView.as_view(), name="purchase-verify"),
    path("purchases/<str:reference>/refresh/", RefreshPaymentView.as_view(), name="purchase-refresh"),
    path("receipts/<uuid:receipt_id>/", ReceiptView.as_view(), name="receipt"),
    path("razorpay/webhook/", RazorpayWebhookView.as_view(), name="razorpay-webhook"),
]
