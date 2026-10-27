"""
Platinum Assisted Matchmaking end to end: the case opened by a verified payment
(Razorpay mocked) or staff activation, matchmaker assignment and scoping,
personalised search, interests (read-only), consent-based contact exchange,
follow-ups, confidentiality and the end of the service period.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import Role
from apps.interactions.models import Interest
from apps.payments.models import Purchase
from apps.payments.tests import PURCHASES, PaymentsTestCase
from apps.profiles.choices import Visibility
from apps.profiles.models import PartnerPreference, Profile
from apps.profiles.test_utils import client_for, make_profile, make_user

from . import assistance
from .entitlements import Feature, entitlements_for
from .models import (
    AssistanceCandidate,
    AssistanceFollowUp,
    AssistanceKind,
    AssistanceNote,
    AssistanceRequest,
    AssistanceStatus,
    ContactConsent,
    ContactExchange,
    Subscription,
    add_months,
)
from .tests import subscribe
from .tests_gold import inline_management, make_staff

IST = ZoneInfo("Asia/Kolkata")
CASES = "/api/v1/memberships/me/assistance/"
EXCHANGES = "/api/v1/memberships/contact-exchanges/"
PLATINUM_PAISE = 23600_00  # ₹20,000 + 18% GST, with the test rate below


def platinum_case(user, starts_at=None) -> AssistanceRequest:
    """A Platinum membership activated as staff or the payments app would, which opens its case."""
    subscription = subscribe(user, "platinum", starts_at=starts_at)
    return assistance.open_service_case(subscription)


@override_settings(MEMBERSHIP_GST_RATE_PERCENT="18")
class PlatinumPurchaseTests(PaymentsTestCase):
    def pay(self, status="captured"):
        response = self.client.post(PURCHASES, {"package": "platinum"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        purchase = Purchase.objects.get(reference=response.json()["purchase"]["reference"])
        payment_id = self.razorpay.pay(purchase.razorpay_order_id, status=status)
        with self.captureOnCommitCallbacks(execute=True):
            self.callback(purchase, payment_id)
        purchase.refresh_from_db()
        return purchase

    def test_verified_payment_activates_three_months_and_opens_one_case(self):
        purchase = self.pay()
        self.assertEqual(purchase.amount_subunits, PLATINUM_PAISE)  # GST added once
        subscription = purchase.subscription
        self.assertEqual((subscription.plan_code, subscription.validity_months), ("platinum", 3))
        self.assertEqual(subscription.ends_at, add_months(subscription.starts_at, 3))
        case = AssistanceRequest.objects.get()
        self.assertEqual((case.kind, case.user, case.subscription, case.status, case.assigned_to),
                         (AssistanceKind.SERVICE, self.user, subscription, AssistanceStatus.REQUESTED, None))

        with self.captureOnCommitCallbacks(execute=True):
            self.callback(purchase, purchase.razorpay_payment_id)
            for event_id in ("evt_1", "evt_1", "evt_2"):
                self.webhook(self.event(purchase, payment_id=purchase.razorpay_payment_id), event_id=event_id)
        self.assertEqual((Subscription.objects.count(), AssistanceRequest.objects.count()), (1, 1))

        mine = self.client.get(CASES).json()
        self.assertTrue(mine["included"])
        self.assertFalse(mine["can_request"])  # the case exists; Platinum doesn't use the Gold request form
        self.assertEqual((mine["requests"][0]["status_label"], mine["requests"][0]["assigned"]), ("Awaiting assignment", False))

    def test_failed_or_pending_payment_opens_nothing(self):
        self.client.post(PURCHASES, {"package": "platinum"}, format="json")
        purchase = Purchase.objects.get()
        for status in ("failed", "authorized"):
            self.callback(purchase, self.razorpay.pay(purchase.razorpay_order_id, status=status))
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(AssistanceRequest.objects.exists())
        self.assertEqual(self.client.get(CASES).json()["requests"], [])


class PlatinumActivationTests(TestCase):
    def test_staff_activation_opens_the_case_once(self):
        user = make_user()
        make_profile(user, gender="male")
        subscription = Subscription.objects.create(user=user, plan_code="platinum")
        admin = Client()
        admin.force_login(make_user(Role.SUPER_ADMIN, is_staff=True, is_superuser=True))
        url = reverse("admin:memberships_subscription_changelist")
        for _ in range(2):
            admin.post(url, {"action": "activate", "_selected_action": [subscription.pk]})
        self.assertEqual(AssistanceRequest.objects.filter(subscription=subscription, kind="service").count(), 1)
        subscription.refresh_from_db()
        self.assertEqual(subscription.ends_at, add_months(subscription.starts_at, 3))

    def test_three_calendar_months_from_month_end(self):
        case = platinum_case(make_user(), starts_at=datetime(2026, 11, 30, 10, 0, tzinfo=IST))
        self.assertEqual(case.subscription.ends_at, datetime(2027, 2, 28, 10, 0, tzinfo=IST))

    def test_other_packages_open_no_service_case_and_keep_their_terms(self):
        for code in ("silver", "gold", "diamond"):  # Royal has its own case: tests_royal.py
            self.assertIsNone(assistance.open_service_case(subscribe(make_user(), code)))
        self.assertFalse(AssistanceRequest.objects.exists())

    def test_platinum_gets_no_self_service_extras(self):
        user = make_user()
        groom = make_profile(user, gender="male")
        platinum_case(user)
        entitlements = entitlements_for(user)
        self.assertTrue(entitlements.has(Feature.PHOTO_VIEWING))  # confirmed by the business for Platinum
        for feature in (Feature.ADVANCED_SEARCH, Feature.MESSAGING, Feature.PROFILE_VIEWERS,
                        Feature.PRIORITY_VISIBILITY, Feature.MATCHMAKING_ASSISTANCE):
            self.assertFalse(entitlements.has(feature), feature)
        self.assertIsNone(entitlements.contact_view_limit)  # no self-service contact quota
        bride = make_profile(gender="female", contact_sharing="paid_members")
        response = client_for(user).post(f"/api/v1/profiles/{bride.profile_code}/contact/")
        self.assertEqual(response.json()["code"], "not_included")
        self.assertEqual(client_for(user).post(CASES, {}, format="json").json()["code"], "upgrade_required")
        self.assertEqual(groom.user, user)


class CaseTestCase(TestCase):
    def setUp(self):
        self.groom = make_profile(gender="male", display_name="Arjun", age=30)
        self.case = platinum_case(self.groom.user)
        self.member = client_for(self.groom.user)
        self.manager = make_staff("assign", first_name="Priya")
        self.matchmaker = make_staff(first_name="Lakshmi", email="lakshmi@example.com")
        self.other_matchmaker = make_staff(first_name="Rani")
        self.bride = make_profile(gender="female", display_name="Meera", age=26)

    def assign(self, to=None):
        assistance.staff_update(self.case, self.manager, status=AssistanceStatus.ASSIGNED, assigned_to=to or self.matchmaker)
        self.case.refresh_from_db()

    def admin(self, user):
        browser = Client()
        browser.force_login(user)
        return browser

    def detail(self, client=None):
        return (client or self.member).get(f"{CASES}{self.case.public_id}/")


class AssignmentTests(CaseTestCase):
    def test_assignment_by_a_manager_to_an_eligible_matchmaker(self):
        self.assertIsNone(self.detail().json()["matchmaker_name"])  # nobody claimed before assignment
        with self.assertRaises(ValueError):
            assistance.staff_update(self.case, self.manager, status=AssistanceStatus.ASSIGNED,
                                    assigned_to=make_user(Role.ADMIN, is_staff=True))  # staff without case rights
        with self.assertRaises(ValueError):
            assistance.staff_update(self.case, self.matchmaker, status=AssistanceStatus.ASSIGNED, assigned_to=self.matchmaker)
        self.assign()
        body = self.detail().json()
        self.assertEqual((body["status"], body["assigned"], body["matchmaker_name"]), ("assigned", True, "Lakshmi"))
        # The matchmaker moves the case on but can't hand it to someone else.
        assistance.staff_update(self.case, self.matchmaker, status=AssistanceStatus.AWAITING_MEMBER, assigned_to=self.matchmaker)
        with self.assertRaises(ValueError):
            assistance.staff_update(self.case, self.matchmaker, status=AssistanceStatus.IN_PROGRESS,
                                    assigned_to=self.other_matchmaker)
        assistance.staff_update(self.case, self.manager, status=AssistanceStatus.IN_PROGRESS, assigned_to=self.other_matchmaker)
        self.assertEqual(
            list(self.case.events.values_list("status", "assigned_to")),
            [("requested", None), ("assigned", self.matchmaker.pk), ("awaiting_member", self.matchmaker.pk),
             ("in_progress", self.other_matchmaker.pk)],
        )

    def test_matchmakers_see_only_their_cases_in_the_admin(self):
        other_case = platinum_case(make_profile(gender="female").user)
        self.assign()
        changelist = reverse("admin:memberships_assistancerequest_changelist")
        listed = self.admin(self.matchmaker).get(changelist).context["cl"].result_list
        self.assertEqual(list(listed), [self.case])
        self.assertEqual(len(self.admin(self.manager).get(changelist).context["cl"].result_list), 2)
        change = reverse("admin:memberships_assistancerequest_change", args=[other_case.pk])
        self.assertIn(self.admin(self.matchmaker).get(change).status_code, (302, 403, 404))
        self.assertNotEqual(self.admin(self.other_matchmaker).get(
            reverse("admin:memberships_assistancerequest_change", args=[self.case.pk])).status_code, 200)
        # Members can't reach the admin at all.
        self.assertNotEqual(self.admin(self.groom.user).get(changelist).status_code, 200)

    def test_members_see_only_their_own_case(self):
        stranger = make_profile(gender="female")
        self.assertEqual(self.detail(client_for(stranger.user)).status_code, 404)
        self.assertEqual(client_for(stranger.user).get(CASES).json()["requests"], [])
        self.assertEqual(client_for().get(f"{CASES}{self.case.public_id}/").status_code, 401)


class NotesAndFollowUpTests(CaseTestCase):
    def test_internal_notes_never_reach_the_member(self):
        self.assign()
        self.case.staff_note = "Internal: family prefers Thrissur."
        self.case.save()
        AssistanceNote.objects.create(request=self.case, author=self.matchmaker, body="Internal: call after 6pm.")
        update = AssistanceNote.objects.create(request=self.case, author=self.matchmaker, body="We shortlisted three profiles.",
                                               visible_to_member=True)
        assistance.note_saved(update, self.matchmaker, True, False)
        AssistanceFollowUp.objects.create(request=self.case, action="Call the family", outcome="Internal outcome",
                                          due_on=timezone.localdate() + timedelta(days=3))
        AssistanceFollowUp.objects.create(request=self.case, action="Review suggestions with you", visible_to_member=True,
                                          awaiting_member=True)
        body = self.detail().json()
        self.assertEqual([item["body"] for item in body["updates"]], ["We shortlisted three profiles."])
        self.assertEqual([(f["action"], f["awaiting_member"]) for f in body["follow_ups"]],
                         [("Review suggestions with you", True)])
        text = self.detail().content.decode()
        for private in ("Internal", "lakshmi@example.com", self.matchmaker.phone_number, "Call the family"):
            self.assertNotIn(private, text)

    def test_admin_inline_records_author_and_notifies_for_member_updates(self):
        self.assign()
        browser = self.admin(self.matchmaker)
        url = reverse("admin:memberships_assistancerequest_change", args=[self.case.pk])
        data = {"status": "in_progress", "member_message": "", "staff_note": "", **inline_management(self.case)}
        data.update({"notes-TOTAL_FORMS": "1", "notes-0-body": "First call done.", "notes-0-visible_to_member": "on",
                     "follow_ups-TOTAL_FORMS": "1", "follow_ups-0-action": "Second call", "follow_ups-0-status": "scheduled",
                     "follow_ups-0-due_on": "2026-11-05"})
        response = browser.post(url, data)
        self.assertEqual(response.status_code, 302, response.content[:2000])
        note, follow_up = AssistanceNote.objects.get(), AssistanceFollowUp.objects.get()
        self.assertEqual((note.author, follow_up.created_by), (self.matchmaker, self.matchmaker))
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, "in_progress")
        self.assertTrue(self.groom.user.notifications.filter(title="New update from your matchmaker").exists())


class SearchAndInterestTests(CaseTestCase):
    def test_find_matches_uses_preferences_and_eligible_profiles_only(self):
        self.assign()
        PartnerPreference.objects.update_or_create(profile=self.groom, defaults={"religions": ["hindu"], "must_haves": ["religion"]})
        christian = make_profile(gender="female", religion="christian", community="")
        hidden = make_profile(gender="female", visibility=Visibility.HIDDEN)
        groom2 = make_profile(gender="male")
        browser = self.admin(self.matchmaker)
        url = reverse("admin:memberships_assistancerequest_find_matches", args=[self.case.pk])
        response = browser.get(url)
        self.assertEqual(response.status_code, 200)
        found = {row["profile"].pk for row in response.context["rows"]}
        self.assertIn(self.bride.pk, found)
        self.assertFalse(found & {christian.pk, hidden.pk, groom2.pk, self.groom.pk})
        self.assertNotIn(self.bride.user.phone_number, response.content.decode())
        filtered = browser.get(url, {"mode": "filters", "religion": "christian"})
        self.assertEqual([row["profile"].pk for row in filtered.context["rows"]], [christian.pk])

        browser.post(url, {"profile": [self.bride.pk, hidden.pk]})
        self.assertEqual(list(AssistanceCandidate.objects.values_list("profile", flat=True)), [self.bride.pk])
        self.assertEqual(self.detail().json()["suggestions"], [])  # not shared yet
        candidate = AssistanceCandidate.objects.get()
        candidate.shared_with_member = True
        candidate.save()
        assistance.candidate_saved(candidate, False)
        suggestion = self.detail().json()["suggestions"][0]
        self.assertEqual((suggestion["profile"]["profile_code"], suggestion["response"]), (self.bride.profile_code, "pending"))
        reply = self.member.post(f"{CASES}{self.case.public_id}/suggestions/{self.bride.profile_code}/",
                                 {"response": "interested"}, format="json")
        self.assertEqual(reply.status_code, 200)
        other = client_for(make_profile(gender="male").user)
        self.assertEqual(other.post(f"{CASES}{self.case.public_id}/suggestions/{self.bride.profile_code}/",
                                    {"response": "interested"}, format="json").status_code, 404)
        self.assertNotIn(self.bride.user.phone_number, self.detail().content.decode())

        # Another matchmaker can't search for this case.
        self.assertNotEqual(self.admin(self.other_matchmaker).get(url).status_code, 200)

    def test_interests_are_shown_read_only_and_never_sent_or_answered_by_staff(self):
        self.assign()
        Interest.objects.create(sender=self.bride, receiver=self.groom)
        response = self.admin(self.matchmaker).get(reverse("admin:memberships_assistancerequest_change", args=[self.case.pk]))
        self.assertContains(response, f"Received from {self.bride.profile_code}")
        before = list(Interest.objects.values_list("pk", "status"))
        browser = self.admin(self.matchmaker)
        browser.post(reverse("admin:memberships_assistancerequest_find_matches", args=[self.case.pk]), {"profile": [self.bride.pk]})
        self.assertEqual(list(Interest.objects.values_list("pk", "status")), before)


class ContactExchangeTests(CaseTestCase):
    def setUp(self):
        super().setUp()
        self.assign()
        self.bride_client = client_for(self.bride.user)
        self.exchange = assistance.start_exchange(self.case, self.bride, self.matchmaker, "Both families asked to talk.")

    def decide(self, client, decision):
        return client.post(f"{EXCHANGES}{self.exchange.public_id}/", {"decision": decision}, format="json")

    def listed(self, client):
        return client.get(EXCHANGES).json()

    def test_numbers_only_after_both_consent_and_disclosure_is_recorded(self):
        for client in (self.member, self.bride_client):
            item = self.listed(client)[0]
            self.assertEqual((item["status"], item["phone_number"], item["my_decision"]), ("pending", None, "pending"))
            self.assertIn("Both families asked to talk.", item["statement"])
        granted = self.decide(self.member, "grant").json()
        self.assertEqual((granted["status"], granted["phone_number"]), ("pending", None))
        self.assertNotIn(self.bride.user.phone_number, self.member.get(EXCHANGES).content.decode())

        shared = self.decide(self.bride_client, "grant").json()
        self.assertEqual((shared["status"], shared["phone_number"]), ("shared", self.groom.user.phone_number))
        self.assertEqual(self.listed(self.member)[0]["phone_number"], self.bride.user.phone_number)
        self.assertTrue(all(c.number_seen_at for c in ContactConsent.objects.all()))
        self.exchange.refresh_from_db()
        self.assertEqual((self.exchange.initiated_by, self.exchange.status), (self.matchmaker, "shared"))
        # The case detail shows the same exchange; nobody else sees it.
        self.assertEqual(self.detail().json()["exchanges"][0]["phone_number"], self.bride.user.phone_number)
        self.assertEqual(self.listed(client_for(make_profile(gender="female").user)), [])

    def test_decline_or_withdrawal_before_both_agree_discloses_nothing(self):
        self.assertEqual(self.decide(self.bride_client, "decline").json()["status"], "declined")
        self.assertEqual(self.decide(self.member, "grant").json()["code"], "closed")
        self.assertIsNone(self.listed(self.member)[0]["phone_number"])

        second = make_profile(gender="female")
        exchange = assistance.start_exchange(self.case, second, self.matchmaker, "Follow-up call.")
        self.member.post(f"{EXCHANGES}{exchange.public_id}/", {"decision": "grant"}, format="json")
        withdrawn = self.member.post(f"{EXCHANGES}{exchange.public_id}/", {"decision": "withdraw"}, format="json").json()
        self.assertEqual(withdrawn["status"], "declined")
        self.assertEqual(client_for(second.user).post(f"{EXCHANGES}{exchange.public_id}/", {"decision": "grant"},
                                                      format="json").json()["code"], "closed")
        self.assertNotIn(second.user.phone_number, self.member.get(EXCHANGES).content.decode())

    def test_only_parties_decide_and_only_the_case_matchmaker_proposes(self):
        outsider = client_for(make_profile(gender="female").user)
        self.assertEqual(self.decide(outsider, "grant").status_code, 404)
        with self.assertRaises(ValueError):
            assistance.start_exchange(self.case, make_profile(gender="female"), self.other_matchmaker, "x")
        with self.assertRaises(ValueError):  # same pair again while pending
            assistance.start_exchange(self.case, self.bride, self.matchmaker, "Again")
        with self.assertRaises(ValueError):  # not a profile the member could be matched with
            assistance.start_exchange(self.case, make_profile(gender="male"), self.matchmaker, "x")
        gold = make_profile(gender="male")
        subscribe(gold.user, "gold")
        gold_case = assistance.request_assistance(gold.user)
        assistance.staff_update(gold_case, self.manager, status=AssistanceStatus.ASSIGNED, assigned_to=self.matchmaker)
        with self.assertRaises(ValueError):  # coordinated exchange is the Platinum service
            assistance.start_exchange(gold_case, make_profile(gender="female"), self.matchmaker, "x")

    def test_admin_proposes_through_the_service_and_never_shows_numbers(self):
        third = make_profile(gender="female")
        browser = self.admin(self.matchmaker)
        response = browser.post(reverse("admin:memberships_contactexchange_add"), {
            "request": self.case.pk, "other_profile": third.pk, "purpose": "Introduce the families.",
            "consents-TOTAL_FORMS": "0", "consents-INITIAL_FORMS": "0", "consents-MIN_NUM_FORMS": "0",
            "consents-MAX_NUM_FORMS": "1000",
        })
        self.assertEqual(response.status_code, 302, response.content[:1500])
        exchange = ContactExchange.objects.get(other_profile=third)
        self.assertEqual((exchange.initiated_by, exchange.consents.count()), (self.matchmaker, 2))
        page = browser.get(reverse("admin:memberships_contactexchange_change", args=[exchange.pk])).content.decode()
        self.assertNotIn(third.user.phone_number, page)
        self.assertNotIn(self.groom.user.phone_number, page)


class ServicePeriodTests(CaseTestCase):
    def test_expiry_keeps_records_and_stops_new_service_actions(self):
        self.assign()
        exchange = assistance.start_exchange(self.case, self.bride, self.matchmaker, "Talk.")
        with self.assertRaises(ValueError):
            assistance.staff_update(self.case, self.matchmaker, status=AssistanceStatus.EXPIRED, assigned_to=self.matchmaker)
        Subscription.objects.filter(pk=self.case.subscription_id).update(ends_at=timezone.now() - timedelta(seconds=1))
        self.case.refresh_from_db()

        body = self.detail().json()
        self.assertEqual((body["status"], body["service_active"]), ("assigned", False))  # not marked completed
        refused = self.member.post(f"{EXCHANGES}{exchange.public_id}/", {"decision": "grant"}, format="json")
        self.assertEqual(refused.json()["code"], "service_ended")
        with self.assertRaises(ValueError):
            assistance.start_exchange(self.case, make_profile(gender="female"), self.matchmaker, "Talk.")
        assistance.staff_update(self.case, self.matchmaker, status=AssistanceStatus.EXPIRED, assigned_to=self.matchmaker)
        self.case.refresh_from_db()
        self.assertFalse(self.case.is_open)
        self.assertTrue(AssistanceRequest.objects.filter(pk=self.case.pk).exists())
        self.assertEqual(ContactExchange.objects.count(), 1)

    def test_cancelled_membership_counts_as_ended(self):
        Subscription.objects.filter(pk=self.case.subscription_id).update(status="cancelled")
        self.assertFalse(self.detail().json()["service_active"])

    def test_unchanged_profiles_api_never_shows_case_data(self):
        self.assign()
        text = client_for(self.bride.user).get(f"/api/v1/profiles/{self.groom.profile_code}/").content.decode()
        self.assertNotIn(str(self.case.public_id), text)
        self.assertEqual(Profile.objects.get(pk=self.groom.pk).partner_preference.must_haves,
                         PartnerPreference(profile=self.groom).must_haves)
