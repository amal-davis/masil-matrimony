"""
Gold features that live in this app, with two or more test members: unlimited
interests, messaging, "who viewed my profile", the shortlist, and the
100-number contact allowance (1st, 100th, 101st, repeats, denials, expiry and
simultaneous requests).
"""
import threading
import unittest
from datetime import timedelta

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.memberships.models import Subscription
from apps.memberships.tests import subscribe
from apps.profiles.models import Profile
from apps.profiles.test_utils import client_for, make_profile

from . import services
from .models import ContactView, Conversation, Interest, Message, Shortlist
from .tests import SEND, SHORTLIST
from .tests_silver import MESSAGES, VIEWERS, accept


class GoldFeatureTests(TestCase):
    """Run again for Diamond (tests_diamond.py)."""

    PLAN = "gold"

    def setUp(self):
        self.groom = make_profile(gender="male", display_name="Arjun")
        self.bride = make_profile(gender="female", display_name="Meera")
        self.subscription = subscribe(self.groom.user, self.PLAN)
        self.client = client_for(self.groom.user)
        self.bride_client = client_for(self.bride.user)

    def test_interests_are_unlimited_and_still_one_per_member(self):
        brides = [make_profile(gender="female") for _ in range(20)]
        for bride in brides:
            self.assertEqual(self.client.post(SEND, {"profile_code": bride.profile_code}, format="json").status_code, 201)
        self.assertEqual(Interest.objects.filter(sender=self.groom).count(), 20)
        self.assertFalse(Interest.objects.filter(sender=self.groom, counts_toward_free_limit=True).exists())
        duplicate = self.client.post(SEND, {"profile_code": brides[0].profile_code}, format="json")
        self.assertEqual(duplicate.status_code, 409)
        # The sender is always the signed-in member: a sender in the body is ignored.
        self.bride_client.post(SEND, {"profile_code": self.groom.profile_code, "sender": self.groom.profile_code}, format="json")
        self.assertTrue(Interest.objects.filter(sender=self.bride, receiver=self.groom).exists())
        self.assertFalse(Interest.objects.filter(sender=self.groom, receiver=self.groom).exists())

    def test_gold_member_starts_a_conversation_and_others_cannot_read_it(self):
        accept(self.groom, self.bride)
        thread = f"{MESSAGES}{self.bride.profile_code}/"
        self.assertEqual(self.client.post(thread, {"body": "Hello"}, format="json").status_code, 201)
        self.assertEqual(self.bride_client.post(f"{MESSAGES}{self.groom.profile_code}/", {"body": "Hi"}, format="json").status_code, 201)
        self.assertEqual(Message.objects.filter(conversation=Conversation.objects.get()).count(), 2)
        outsider = make_profile(gender="male")
        subscribe(outsider.user, self.PLAN)
        reading = client_for(outsider.user).get(thread).json()
        self.assertEqual(reading["results"], [])  # their own (empty) conversation, never this one
        self.assertEqual(reading["messaging"]["code"], "interest_required")
        # No accepted interest: Gold doesn't override that rule.
        stranger = make_profile(gender="female")
        response = self.client.post(f"{MESSAGES}{stranger.profile_code}/", {"body": "Hello"}, format="json")
        self.assertEqual((response.status_code, response.json()["code"]), (403, "interest_required"))

    def test_gold_owner_sees_who_viewed(self):
        client_for(self.bride.user).get(f"/api/v1/profiles/{self.groom.profile_code}/")
        body = self.client.get(VIEWERS).json()
        self.assertEqual([item["profile"]["profile_code"] for item in body["results"]], [self.bride.profile_code])

    def test_shortlist_persists_and_is_private(self):
        self.assertEqual(self.client.post(SHORTLIST, {"profile_code": self.bride.profile_code}, format="json").status_code, 201)
        self.client.post(SHORTLIST, {"profile_code": self.bride.profile_code}, format="json")
        self.assertEqual(Shortlist.objects.filter(owner=self.groom).count(), 1)
        # A new session (new client) sees the same saved list.
        self.assertEqual(client_for(self.groom.user).get(SHORTLIST).json()["count"], 1)
        other = make_profile(gender="male")
        client_for(other.user).delete(f"{SHORTLIST}{self.bride.profile_code}/")
        self.assertEqual(client_for(other.user).get(SHORTLIST).json()["count"], 0)
        self.assertEqual(Shortlist.objects.filter(owner=self.groom).count(), 1)


class GoldContactAllowanceTests(TestCase):
    """100 different members' numbers per Gold membership; viewing one again is free. Diamond: tests_diamond.py."""

    PLAN = "gold"

    def setUp(self):
        self.groom = make_profile(gender="male")
        self.subscription = subscribe(self.groom.user, self.PLAN)
        self.client = client_for(self.groom.user)
        self.brides = [make_profile(gender="female", contact_sharing="paid_members") for _ in range(101)]

    def view(self, profile):
        return self.client.post(f"/api/v1/profiles/{profile.profile_code}/contact/")

    def test_first_hundredth_and_hundred_and_first(self):
        first = self.view(self.brides[0]).json()
        self.assertEqual((first["used"], first["limit"], first["phone_number"]), (1, 100, self.brides[0].user.phone_number))
        for bride in self.brides[1:99]:
            self.assertEqual(self.view(bride).status_code, 200)
        hundredth = self.view(self.brides[99]).json()
        self.assertEqual((hundredth["used"], hundredth["phone_number"]), (100, self.brides[99].user.phone_number))

        refused = self.view(self.brides[100])
        self.assertEqual((refused.status_code, refused.json()["code"]), (403, "limit_reached"))
        self.assertNotIn(self.brides[100].user.phone_number, refused.content.decode())
        self.assertEqual(self.view(self.brides[0]).json()["used"], 100)  # already viewed: still free

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.contact_views_used, 100)
        self.assertEqual(ContactView.objects.filter(subscription=self.subscription).count(), 100)
        entitlements = self.client.get("/api/v1/memberships/me/").json()["entitlements"]
        self.assertEqual((entitlements["contact_views_used"], entitlements["contact_views_remaining"]), (100, 0))

    def test_repeats_denials_and_expiry(self):
        for _ in range(3):
            self.view(self.brides[0])
        Profile.objects.filter(pk=self.brides[1].pk).update(contact_sharing="hidden")
        self.assertEqual(self.view(self.brides[1]).json()["code"], "not_shared")
        self.assertEqual(self.view(make_profile(gender="male", contact_sharing="paid_members")).json()["code"], "same_gender")
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.contact_views_used, 1)

        Subscription.objects.filter(pk=self.subscription.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.view(self.brides[2]).json()["code"], "not_included")
        self.assertEqual(ContactView.objects.count(), 1)  # the record is kept

    def test_numbers_never_appear_outside_the_contact_flow(self):
        self.view(self.brides[0])
        number = self.brides[0].user.phone_number
        for url in ("/api/v1/profiles/search/", "/api/v1/profiles/matches/", f"/api/v1/profiles/{self.brides[0].profile_code}/",
                    "/api/v1/dashboard/summary/", "/api/v1/memberships/me/"):
            with self.subTest(url=url):
                self.assertNotIn(number, self.client.get(url).content.decode())


@unittest.skipUnless(connection.vendor == "mysql", "needs MySQL/MariaDB row locks")
class GoldConcurrentContactViewTests(TransactionTestCase):
    serialized_rollback = True
    PLAN = "gold"

    def test_simultaneous_unlocks_stop_at_one_hundred(self):
        groom = make_profile(gender="male")
        subscription = subscribe(groom.user, self.PLAN)
        brides = [make_profile(gender="female", contact_sharing="paid_members") for _ in range(5)]
        services.view_contact(groom, brides[0].profile_code)
        Subscription.objects.filter(pk=subscription.pk).update(contact_views_used=99)  # one left

        results, barrier = [], threading.Barrier(4)

        def unlock(bride):
            try:
                barrier.wait()
                services.view_contact(Profile.objects.get(pk=groom.pk), bride.profile_code)
                results.append("ok")
            except services.InteractionError as error:
                results.append(error.code)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=unlock, args=(bride,)) for bride in brides[1:]]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        subscription.refresh_from_db()
        self.assertEqual(sorted(results), ["limit_reached"] * 3 + ["ok"])
        self.assertEqual(subscription.contact_views_used, 100)
