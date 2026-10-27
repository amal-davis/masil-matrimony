"""
Royal Exclusive At-Home Matchmaking end to end: verified payment (Razorpay
mocked) at the stated price, the 12-month case, assignment, the service plan,
curation, at-home consultations, family coordination with permission, contact
exchange with consent, confidentiality and the end of the service period.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.payments.models import Purchase
from apps.payments.tests import PURCHASES, PaymentsTestCase
from apps.profiles.choices import Visibility
from apps.profiles.models import PartnerPreference, Profile
from apps.profiles.test_utils import client_for, make_profile, make_user

from . import assistance
from .entitlements import FEATURE_PACKAGES, Feature, entitlements_for
from .models import (
    AssistanceCandidate,
    AssistanceRequest,
    AssistanceStatus,
    Consultation,
    ConsultationStatus,
    FamilyContact,
    FamilyCoordination,
    Subscription,
    add_months,
)
from .tests import subscribe
from .tests_gold import inline_management, make_staff
from .tests_platinum import CASES, EXCHANGES

IST = ZoneInfo("Asia/Kolkata")
ROYAL_PAISE = 118000_00


def royal_case(user, starts_at=None) -> AssistanceRequest:
    return assistance.open_service_case(subscribe(user, "royal", starts_at=starts_at))


class RoyalPurchaseTests(PaymentsTestCase):
    def pay(self, status="captured"):
        response = self.client.post(PURCHASES, {"package": "royal"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        purchase = Purchase.objects.get(reference=response.json()["purchase"]["reference"])
        with self.captureOnCommitCallbacks(execute=True):
            self.callback(purchase, self.razorpay.pay(purchase.razorpay_order_id, status=status))
        purchase.refresh_from_db()
        return purchase

    def test_verified_payment_at_the_stated_price_opens_one_twelve_month_case(self):
        purchase = self.pay()
        self.assertEqual(
            (purchase.base_amount, purchase.gst_rate, purchase.gst_amount, purchase.total_amount, purchase.amount_subunits),
            (Decimal("100000.00"), Decimal("18.00"), Decimal("18000.00"), Decimal("118000.00"), ROYAL_PAISE),
        )
        subscription = purchase.subscription
        self.assertEqual((subscription.plan_code, subscription.validity_months), ("royal", 12))
        self.assertEqual(subscription.ends_at, add_months(subscription.starts_at, 12))
        case = AssistanceRequest.objects.get()
        self.assertEqual((case.kind, case.subscription, case.status, case.assigned_to),
                         ("service", subscription, AssistanceStatus.REQUESTED, None))
        self.assertFalse(Consultation.objects.exists())  # nothing scheduled automatically

        with self.captureOnCommitCallbacks(execute=True):
            for event_id in ("evt_1", "evt_1", "evt_2"):
                self.webhook(self.event(purchase, payment_id=purchase.razorpay_payment_id), event_id=event_id)
            self.callback(purchase, purchase.razorpay_payment_id)
        self.assertEqual((Subscription.objects.count(), AssistanceRequest.objects.count()), (1, 1))

        # The receipt and the package list carry the same figures as the order.
        receipt = self.client.get(f"/api/v1/payments/receipts/{purchase.receipt.public_id}/").content.decode()
        for amount in ("100000.00", "18000.00", "118000.00"):
            self.assertIn(amount, receipt)
        royal = next(p for p in self.client.get("/api/v1/memberships/packages/").json() if p["code"] == "royal")
        self.assertEqual((royal["fee"], royal["gst_rate"], royal["gst_amount"], royal["total_payable"]),
                         ("100000.00", "18.00", "18000.00", "118000.00"))

    @override_settings(MEMBERSHIP_GST_RATE_PERCENT="12")
    def test_the_applicable_rate_setting_never_changes_royals_stated_price(self):
        self.assertEqual(self.pay().amount_subunits, ROYAL_PAISE)

    def test_failed_or_pending_payment_opens_nothing(self):
        self.client.post(PURCHASES, {"package": "royal"}, format="json")
        purchase = Purchase.objects.get()
        for status in ("failed", "authorized"):
            self.callback(purchase, self.razorpay.pay(purchase.razorpay_order_id, status=status))
        self.assertFalse(Subscription.objects.exists() or AssistanceRequest.objects.exists())


class RoyalTermsTests(TestCase):
    def test_twelve_calendar_months_from_month_end(self):
        case = royal_case(make_user(), starts_at=datetime(2028, 2, 29, 10, 0, tzinfo=IST))
        self.assertEqual(case.subscription.ends_at, datetime(2029, 2, 28, 10, 0, tzinfo=IST))

    def test_royal_grants_no_online_package_extras(self):
        user = make_user()
        royal_case(user)
        granted = {feature for feature in FEATURE_PACKAGES if entitlements_for(user).has(feature)}
        self.assertEqual(granted, {Feature.PHOTO_VIEWING})
        self.assertIsNone(entitlements_for(user).contact_view_limit)


class RoyalCaseTestCase(TestCase):
    def setUp(self):
        self.member_profile = make_profile(gender="female", display_name="Anjali", age=27)
        self.case = royal_case(self.member_profile.user)
        self.member = client_for(self.member_profile.user)
        self.manager = make_staff("assign")
        self.matchmaker = make_staff(first_name="Devika", email="devika@example.com")
        self.other_matchmaker = make_staff(first_name="Rani")
        assistance.staff_update(self.case, self.manager, status=AssistanceStatus.ASSIGNED, assigned_to=self.matchmaker)
        self.case.refresh_from_db()
        self.url = f"{CASES}{self.case.public_id}/"

    def detail(self, client=None):
        return (client or self.member).get(self.url)

    def admin(self, user):
        browser = Client()
        browser.force_login(user)
        return browser


class ServicePlanAndStatusTests(RoyalCaseTestCase):
    def test_member_requirements_and_staff_plan_stay_apart(self):
        response = self.member.patch(f"{self.url}requirements/", {"requirements": "A doctor, settled in Kerala."}, format="json")
        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.case.service_plan, self.case.next_steps = "Focus on Kochi families.", "Review five profiles."
        self.case.staff_note = "Internal: father decides."
        self.case.save()
        body = self.detail().json()
        self.assertEqual((body["requirements"], body["service_plan"], body["next_steps"]),
                         ("A doctor, settled in Kerala.", "Focus on Kochi families.", "Review five profiles."))
        self.assertEqual(body["features"], {"contact_exchange": True, "consultations": True, "family": True})
        self.assertNotIn("Internal", self.detail().content.decode())
        # Members change only their own words, on their own case.
        other = client_for(make_profile(gender="male").user)
        self.assertEqual(other.patch(f"{self.url}requirements/", {"requirements": "x"}, format="json").status_code, 404)
        self.assertEqual(self.member.patch(self.url, {"status": "completed"}, format="json").status_code, 405)

    def test_stages_need_the_records_they_claim(self):
        assistance.staff_update(self.case, self.matchmaker, status=AssistanceStatus.REQUIREMENTS, assigned_to=self.matchmaker)
        for status in (AssistanceStatus.CONSULTATION_SCHEDULED, AssistanceStatus.FAMILY):
            with self.assertRaises(ValueError):
                assistance.staff_update(self.case, self.matchmaker, status=status, assigned_to=self.matchmaker)
        platinum = assistance.open_service_case(subscribe(make_profile(gender="male").user, "platinum"))
        assistance.staff_update(platinum, self.manager, status=AssistanceStatus.ASSIGNED, assigned_to=self.matchmaker)
        with self.assertRaises(ValueError):  # Royal stages are Royal's
            assistance.staff_update(platinum, self.matchmaker, status=AssistanceStatus.CURATION, assigned_to=self.matchmaker)

    def test_matchmakers_see_only_their_royal_cases(self):
        url = reverse("admin:memberships_assistancerequest_change", args=[self.case.pk])
        self.assertEqual(self.admin(self.matchmaker).get(url).status_code, 200)
        self.assertNotEqual(self.admin(self.other_matchmaker).get(url).status_code, 200)
        self.assertEqual(self.detail(client_for(make_profile(gender="male").user)).status_code, 404)


class CurationTests(RoyalCaseTestCase):
    def test_curated_profiles_from_preferences_rechecked_when_shared_and_shown(self):
        PartnerPreference.objects.update_or_create(
            profile=self.member_profile, defaults={"religions": ["hindu"], "must_haves": ["religion"]}
        )
        match = make_profile(gender="male", display_name="Rahul")
        other_faith = make_profile(gender="male", religion="muslim", community="")
        browser = self.admin(self.matchmaker)
        find = reverse("admin:memberships_assistancerequest_find_matches", args=[self.case.pk])
        found = {row["profile"].pk for row in browser.get(find).context["rows"]}
        self.assertIn(match.pk, found)
        self.assertNotIn(other_faith.pk, found)
        browser.post(find, {"profile": [match.pk]})
        candidate = AssistanceCandidate.objects.get()
        self.assertEqual(assistance.candidate_status(candidate), "recommended")
        self.assertEqual(self.detail().json()["suggestions"], [])

        # Hidden since it was found: the admin refuses to share it.
        Profile.objects.filter(pk=match.pk).update(visibility=Visibility.HIDDEN)
        change = reverse("admin:memberships_assistancerequest_change", args=[self.case.pk])
        data = {"status": "assigned", "assigned_to": "", "member_message": "", "service_plan": "", "next_steps": "",
                "staff_note": "", **inline_management(self.case)}
        data.update({"candidates-0-profile": str(match.pk), "candidates-0-shared_with_member": "on",
                     "candidates-0-staff_note": "", **royal_inline_management(self.case)})
        self.assertEqual(browser.post(change, data).status_code, 200)  # redisplayed with the error
        candidate.refresh_from_db()
        self.assertFalse(candidate.shared_with_member)

        Profile.objects.filter(pk=match.pk).update(visibility=Visibility.MEMBERS)
        self.assertEqual(browser.post(change, data).status_code, 302)
        suggestion = self.detail().json()["suggestions"][0]
        self.assertEqual((suggestion["status"], suggestion["profile"]["profile_code"]), ("shared", match.profile_code))
        self.member.post(f"{self.url}suggestions/{match.profile_code}/", {"response": "not_interested"}, format="json")
        self.assertEqual(self.detail().json()["suggestions"][0]["status"], "declined")

        Profile.objects.filter(pk=match.pk).update(visibility=Visibility.HIDDEN)
        gone = self.detail().json()["suggestions"][0]
        self.assertEqual((gone["status"], gone["profile"]), ("no_longer_available", None))
        self.assertNotIn(match.user.phone_number, self.detail().content.decode())


def royal_inline_management(item) -> dict:
    data = {}
    for prefix, rows in (("consultations", item.consultations), ("family_contacts", item.family_contacts)):
        ids = list(rows.values_list("pk", flat=True))
        data.update({f"{prefix}-TOTAL_FORMS": str(len(ids)), f"{prefix}-INITIAL_FORMS": str(len(ids)),
                     f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000"})
        for index, pk in enumerate(ids):
            data.update({f"{prefix}-{index}-id": str(pk), f"{prefix}-{index}-request": str(item.pk)})
    data.update({"candidates-TOTAL_FORMS": str(item.candidates.count()), "candidates-INITIAL_FORMS": str(item.candidates.count())})
    for index, pk in enumerate(item.candidates.values_list("pk", flat=True)):
        data.update({f"candidates-{index}-id": str(pk), f"candidates-{index}-request": str(item.pk)})
    return data


class ConsultationTests(RoyalCaseTestCase):
    ADDRESS = "12 Lotus Gardens, Kochi 682001"

    def request(self):
        response = self.member.post(f"{self.url}consultations/", {"note": "Weekends", "address": self.ADDRESS}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return Consultation.objects.get(public_id=response.json()["id"])

    def member_action(self, consultation, action):
        return self.member.post(f"{self.url}consultations/{consultation.public_id}/", {"action": action}, format="json")

    def test_request_propose_confirm_reschedule_complete(self):
        consultation = self.request()
        body = self.detail().json()["consultations"][0]
        self.assertEqual((body["status"], body["location_provided"], body["scheduled_for"]), ("requested", True, None))
        self.assertNotIn("Lotus Gardens", self.detail().content.decode())  # the address never comes back
        self.assertEqual(self.member.post(f"{self.url}consultations/", {}, format="json").json()["code"], "already_requested")
        with self.assertRaises(ValueError):  # no scheduled visit yet
            assistance.staff_update(self.case, self.matchmaker, status=AssistanceStatus.CONSULTATION_SCHEDULED,
                                    assigned_to=self.matchmaker)

        when = timezone.now() + timedelta(days=3)
        assistance.staff_consultation(consultation, self.matchmaker, "propose", when=when, message="Saturday 11 am?")
        self.assertEqual(self.detail().json()["consultations"][0]["status"], "proposed")  # not scheduled yet
        self.assertEqual(self.member_action(consultation, "confirm").json()["status"], "scheduled")
        assistance.staff_update(self.case, self.matchmaker, status=AssistanceStatus.CONSULTATION_SCHEDULED,
                                assigned_to=self.matchmaker)
        with self.assertRaises(ValueError):  # the visit hasn't happened
            assistance.staff_consultation(consultation, self.matchmaker, "complete", outcome="Met the family.")

        later = timezone.now() + timedelta(days=5)
        assistance.staff_consultation(consultation, self.matchmaker, "propose", when=later)  # reschedule
        consultation.refresh_from_db()
        self.assertEqual((consultation.status, consultation.confirmed_at), (ConsultationStatus.PROPOSED, None))
        self.member_action(consultation, "confirm")
        Consultation.objects.filter(pk=consultation.pk).update(scheduled_for=timezone.now() - timedelta(hours=1))
        assistance.staff_consultation(consultation, self.matchmaker, "complete", outcome="Internal: met the parents.")
        body = self.detail().json()["consultations"][0]
        self.assertEqual(body["status"], "completed")
        self.assertNotIn("met the parents", self.detail().content.decode())
        self.assertEqual(list(consultation.events.values_list("status", flat=True)),
                         ["requested", "proposed", "scheduled", "proposed", "scheduled", "completed"])

    def test_cancel_unavailable_and_who_may_act(self):
        consultation = self.request()
        with self.assertRaises(ValueError):
            assistance.staff_consultation(consultation, self.other_matchmaker, "propose",
                                          when=timezone.now() + timedelta(days=1))
        assistance.staff_consultation(consultation, self.matchmaker, "unavailable", message="No visits in your area yet.")
        self.assertEqual(self.detail().json()["consultations"][0]["message"], "No visits in your area yet.")
        second = self.request()
        self.assertEqual(self.member_action(second, "cancel").json()["status"], "cancelled")
        self.assertEqual(self.member_action(second, "confirm").json()["code"], "nothing_to_confirm")
        stranger = client_for(make_profile(gender="male").user)
        self.assertEqual(stranger.post(f"{self.url}consultations/{second.public_id}/", {"action": "cancel"},
                                       format="json").status_code, 404)

    def test_address_only_for_the_cases_staff(self):
        consultation = self.request()
        url = reverse("admin:memberships_consultation_change", args=[consultation.pk])
        self.assertContains(self.admin(self.matchmaker).get(url), "Lotus Gardens")
        self.assertNotEqual(self.admin(self.other_matchmaker).get(url).status_code, 200)
        changelist = self.admin(self.other_matchmaker).get(reverse("admin:memberships_consultation_changelist"))
        self.assertNotContains(changelist, "Lotus Gardens")
        profile_text = client_for(make_profile(gender="male").user).get(
            f"/api/v1/profiles/{self.member_profile.profile_code}/").content.decode()
        self.assertNotIn("Lotus", profile_text)

    def test_platinum_has_no_home_visits(self):
        platinum = assistance.open_service_case(subscribe(make_profile(gender="male").user, "platinum"))
        response = client_for(platinum.user).post(f"{CASES}{platinum.public_id}/consultations/", {}, format="json")
        self.assertEqual(response.status_code, 403)


class FamilyCoordinationTests(RoyalCaseTestCase):
    def add(self, **extra):
        data = {"name": "Suresh", "relationship": "Father", "phone_number": "+919811112222",
                "purpose": "Discuss suggested profiles with the family.", "permission": True, **extra}
        return self.member.post(f"{self.url}family/", data, format="json")

    def test_member_permission_is_required_and_withdrawal_stops_coordination(self):
        self.assertEqual(self.add(permission=False).status_code, 400)
        response = self.add()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual((body["permission"], body["phone_hint"]), ("granted", "•••• 2222"))
        self.assertIn("for this purpose only", body["statement"])
        self.assertNotIn("+919811112222", self.detail().content.decode())
        contact = FamilyContact.objects.get()

        action = assistance.record_family_action(contact, self.matchmaker, "Called to introduce the service",
                                                 outcome="Internal: prefers evenings", visible=True)
        assistance.staff_update(self.case, self.matchmaker, status=AssistanceStatus.FAMILY, assigned_to=self.matchmaker)
        family = self.detail().json()["family"][0]
        self.assertEqual([item["action"] for item in family["actions"]], [action.action])
        self.assertNotIn("prefers evenings", self.detail().content.decode())

        withdrawn = self.member.post(f"{self.url}family/{contact.public_id}/", {"decision": "withdraw"}, format="json")
        self.assertEqual(withdrawn.json()["permission"], "withdrawn")
        with self.assertRaises(ValueError):
            assistance.record_family_action(contact, self.matchmaker, "Call again")
        self.assertEqual(FamilyCoordination.objects.count(), 1)

    def test_staff_suggestions_wait_for_the_member(self):
        contact = assistance.add_family_contact(self.case, self.matchmaker, name="Lakshmi", relationship="Aunt",
                                                purpose="Arrange a family meeting.")
        self.assertEqual(contact.permission, "pending")
        with self.assertRaises(ValueError):
            assistance.record_family_action(contact, self.matchmaker, "Call")
        with self.assertRaises(ValueError):
            assistance.staff_update(self.case, self.matchmaker, status=AssistanceStatus.FAMILY, assigned_to=self.matchmaker)
        self.member.post(f"{self.url}family/{contact.public_id}/", {"decision": "grant"}, format="json")
        assistance.record_family_action(contact, self.matchmaker, "Called the aunt")
        with self.assertRaises(ValueError):  # another matchmaker
            assistance.record_family_action(contact, self.other_matchmaker, "Call")
        stranger = client_for(make_profile(gender="male").user)
        self.assertEqual(stranger.post(f"{self.url}family/{contact.public_id}/", {"decision": "withdraw"},
                                       format="json").status_code, 404)

    def test_admin_offers_only_permitted_contacts(self):
        self.add()
        pending = assistance.add_family_contact(self.case, self.matchmaker, name="Ravi", relationship="Brother",
                                                purpose="x")
        browser = self.admin(self.matchmaker)
        form = browser.get(reverse("admin:memberships_familycoordination_add")).context["adminform"].form
        self.assertNotIn(pending, form.fields["contact"].queryset)
        self.assertEqual(form.fields["contact"].queryset.count(), 1)
        other_form = self.admin(self.other_matchmaker).get(
            reverse("admin:memberships_familycoordination_add")).context["adminform"].form
        self.assertEqual(other_form.fields["contact"].queryset.count(), 0)


class RoyalContactAndExpiryTests(RoyalCaseTestCase):
    def test_contact_exchange_needs_both_consents(self):
        groom = make_profile(gender="male")
        exchange = assistance.start_exchange(self.case, groom, self.matchmaker, "Families agreed to talk.")
        url = f"{EXCHANGES}{exchange.public_id}/"
        self.assertIsNone(self.member.post(url, {"decision": "grant"}, format="json").json()["phone_number"])
        shared = client_for(groom.user).post(url, {"decision": "grant"}, format="json").json()
        self.assertEqual(shared["phone_number"], self.member_profile.user.phone_number)

    def test_expiry_keeps_every_record_and_stops_new_service(self):
        consultation = assistance.request_consultation(self.case, self.member_profile.user, "", "Kochi")
        self.member.post(f"{self.url}family/", {"name": "Suresh", "relationship": "Father", "purpose": "Talk",
                                                "permission": True}, format="json")
        Subscription.objects.filter(pk=self.case.subscription_id).update(ends_at=timezone.now() - timedelta(seconds=1))
        body = self.detail().json()
        self.assertEqual((body["service_active"], body["status"]), (False, "assigned"))
        self.assertEqual(len(body["consultations"]) + len(body["family"]), 2)
        with self.assertRaises(ValueError):
            assistance.staff_consultation(consultation, self.matchmaker, "propose", when=timezone.now() + timedelta(days=1))
        self.assertEqual(self.member.post(f"{self.url}consultations/", {}, format="json").status_code, 403)
        with self.assertRaises(ValueError):
            assistance.record_family_action(FamilyContact.objects.get(), self.matchmaker, "Call")
        assistance.staff_update(self.case, self.matchmaker, status=AssistanceStatus.EXPIRED, assigned_to=self.matchmaker)
        self.assertTrue(Consultation.objects.exists() and FamilyContact.objects.exists())
