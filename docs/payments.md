# Membership payments (Razorpay)

How members buy a package online, and how to set it up. Code: `backend/apps/payments/`,
`frontend/features/payments/`, `frontend/app/(dashboard)/dashboard/membership/`.

## Flow

1. **Checkout page** `/dashboard/membership/checkout/<package>` shows the price from
   `GET /api/v1/payments/checkout/<package>/` (the package's own fee and GST; nothing is calculated in the browser).
2. **Pay now** → `POST /api/v1/payments/purchases/ {"package": "royal"}`. The API records a `Purchase`
   (snapshot of package, fee, GST, total, validity, billing name/email/phone) and creates a Razorpay order
   for exactly that total in paise. A repeat request within 30 minutes reuses the unpaid order.
3. The browser opens Razorpay Standard Checkout (`checkout.razorpay.com/v1/checkout.js`) with that order.
4. On success the browser sends Razorpay's response to `POST .../purchases/<ref>/verify/`. The API checks
   `HMAC_SHA256(<stored order id>|<payment id>, key secret)`, then **asks Razorpay's API**
   (`GET /v1/orders/<id>/payments`) for the order's payments.
5. Only a payment Razorpay reports as **captured**, for this order, with exactly this amount and currency,
   activates the membership: one `Subscription`, under a row lock, exactly once. "Authorised" is not paid.
6. **Webhooks** (`POST /api/v1/payments/razorpay/webhook/`) do the same check independently, so a member who
   closes the browser after paying is still activated. Duplicate and out-of-order events change nothing.
7. After activation a **payment receipt** is numbered (`MM/2026-27/000001`) and emailed to the billing
   email. Email failures never affect the payment; they're retried (`retry_receipt_emails`, or the admin).

Purchase rules: a member with a current paid membership can't buy another online (they contact the team).
If a payment is confirmed while one is active anyway, the new one starts when the current one ends.
Refunds are handled in the Razorpay Dashboard; a refund does not automatically end the membership: staff
cancel it in the admin.

## Configure test mode

In `backend/.env` (never in source files, never in a `NEXT_PUBLIC_` variable):

| Variable | Value |
|---|---|
| `RAZORPAY_MODE` | `test` |
| `RAZORPAY_KEY_ID` | Dashboard (Test Mode) > Account & Settings > API Keys: Key Id (`rzp_test_…`) |
| `RAZORPAY_KEY_SECRET` | the Key Secret shown with it |
| `RAZORPAY_WEBHOOK_SECRET` | the secret you type when creating the webhook (below) |
| `MEMBERSHIP_GST_RATE_PERCENT` | only once confirmed; until then only Royal (stated 18%) can be bought |
| `EMAIL_PROVIDER` etc. | `console` prints receipt emails in the backend terminal; `smtp` sends them |

Restart `python manage.py runserver` after changing `.env`.

In the Razorpay Dashboard (test mode), enable **automatic capture** (Account & Settings > Payment Capture).
Without it payments stay "authorised" and no membership is activated.

### Webhook

Dashboard > Account & Settings > Webhooks > Add new webhook:

- URL: `https://<your API host>/api/v1/payments/razorpay/webhook/` (Razorpay must reach it from the internet:
  for local testing use a tunnel such as ngrok pointing at port 8000, and add its host to `DJANGO_ALLOWED_HOSTS`).
- Secret: a long random value; put the same value in `RAZORPAY_WEBHOOK_SECRET`.
- Events: `payment.authorized`, `payment.captured`, `payment.failed`, `order.paid`.

Without a reachable webhook, payments still complete through the browser callback and the
"Check payment status" button.

### Try it

1. Log in as a member with an email address and no active membership.
2. Membership & Upgrade > Buy Royal > tick the terms > Pay.
3. In the Razorpay window use a test card or UPI ID from Razorpay's "Test card details" documentation.
4. You land on the purchase page: Paid, membership dates, and a receipt (printed in the backend terminal
   with `EMAIL_PROVIDER=console`). Try a failing test card and closing the window too.

## Go-live checklist

- [ ] Accountant confirms GST treatment of each package; set `MEMBERSHIP_GST_RATE_PERCENT` (or keep packages unavailable).
- [ ] Decide whether a GST **tax invoice** is required. The app issues payment receipts only; a tax invoice also
      needs GSTIN, legal name and address, SAC code, place of supply and the CGST/SGST vs IGST split.
- [ ] `BILLING_SELLER_NAME`, `BILLING_SELLER_ADDRESS` (required for live), `BILLING_SELLER_GSTIN`,
      `BILLING_CONTACT_EMAIL`, `BILLING_CONTACT_PHONE` set to the confirmed details.
- [ ] Razorpay account activated (KYC), live API keys generated; `RAZORPAY_MODE=live`, `rzp_live_` key id and secret.
- [ ] Live-mode webhook created with a new secret; `RAZORPAY_WEBHOOK_SECRET` updated.
- [ ] Automatic capture enabled in live mode.
- [ ] `EMAIL_PROVIDER=smtp` with a working sender (`python manage.py send_test_email you@example.com`).
- [ ] Cron: `python manage.py retry_receipt_emails` every few minutes; `purge_otp_challenges` daily.
- [ ] Refund & Cancellation Policy and Terms reviewed for online payment.
- [ ] One real low-value payment end to end, then refund it from the Dashboard.

Production settings refuse to start in live mode while the webhook secret, seller name/address or SMTP is missing.
