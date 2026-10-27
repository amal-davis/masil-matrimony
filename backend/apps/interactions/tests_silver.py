"""
Silver features that live in this app: personal messaging, "who viewed my
profile" and the 40-number contact allowance, with two or more test members.
"""
import threading
import unittest
from datetime import timedelta

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.memberships.models import Subscription
from apps.memberships.tests import subscribe
from apps.notifications.models import Notification
from apps.profiles.choices import PhotoVisibility, ProfileStatus, Visibility
from apps.profiles.models import Profile
from apps.profiles.test_utils import client_for, make_profile
from apps.profiles.tests import walk_keys

from . import services
from .models import ContactView, Conversation, Interest, InterestStatus, Message, ProfileView
from .profile_views import VISIT_GAP

MESSAGES = "/api/v1/messages/"
VIEWERS = "/api/v1/profile-views/"
PRIVATE_KEYS = ("phone_number", "email", "date_of_birth", "contact_sharing", "user", "id", "public_id", "about")


def accept(sender: Profile, receiver: Profile) -> Interest:
    return Interest.objects.create(
        sender=sender, receiver=receiver, status=InterestStatus.ACCEPTED, responded_at=timezone.now()
    )


class MessagingTests(TestCase):
    def setUp(self):
        self.groom = make_profile(gender="male", display_name="Arjun")
        self.bride = make_profile(gender="female", display_name="Meera")
        self.subscription = subscribe(self.groom.user, "silver")
        accept(self.groom, self.bride)
        self.groom_client = client_for(self.groom.user)
        self.bride_client = client_for(self.bride.user)

    def thread(self, client, other):
        return f"{MESSAGES}{other.profile_code}/"

    def send(self, client, other, body="Hello, may we talk?"):
        return client.post(self.thread(client, other), {"body": body}, format="json")

    def test_silver_member_writes_and_free_member_reads_and_replies(self):
        response = self.send(self.groom_client, self.bride)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()["mine"])
        self.assertTrue(Notification.objects.filter(recipient=self.bride.user, kind="message_received").exists())

        inbox = self.bride_client.get(MESSAGES).json()
        self.assertEqual(inbox["count"], 1)
        self.assertEqual((inbox["results"][0]["unread"], inbox["results"][0]["profile"]["profile_code"]),
                         (1, self.groom.profile_code))

        thread = self.bride_client.get(self.thread(self.bride_client, self.groom)).json()
        self.assertEqual([m["body"] for m in thread["results"]], ["Hello, may we talk?"])
        self.assertFalse(thread["results"][0]["mine"])
        # The bride is on Free: she may reply because the groom wrote first.
        self.assertEqual(thread["messaging"]["code"], "available")
        self.assertEqual(self.bride_client.get(MESSAGES).json()["results"][0]["unread"], 0)  # opened = read

        self.assertEqual(self.send(self.bride_client, self.groom, "Yes, of course.").status_code, 201)
        thread = self.groom_client.get(self.thread(self.groom_client, self.bride)).json()
        self.assertEqual([m["body"] for m in thread["results"]], ["Yes, of course.", "Hello, may we talk?"])
        self.assertEqual(Message.objects.count(), 2)  # stored in the database
        self.assertEqual(Conversation.objects.get().started_by, self.groom)

    def test_free_member_cannot_start_a_conversation(self):
        response = self.send(self.bride_client, self.groom)
        self.assertEqual((response.status_code, response.json()["code"]), (403, "upgrade_required"))
        self.assertFalse(Conversation.objects.exists())
        status = self.bride_client.get(self.thread(self.bride_client, self.groom)).json()["messaging"]
        self.assertEqual((status["can_send"], status["code"]), (False, "upgrade_required"))

    def test_an_accepted_interest_is_needed(self):
        Interest.objects.update(status=InterestStatus.PENDING)
        response = self.send(self.groom_client, self.bride)
        self.assertEqual((response.status_code, response.json()["code"]), (403, "interest_required"))
        Interest.objects.all().delete()
        self.assertEqual(self.send(self.groom_client, self.bride).json()["code"], "interest_required")
        self.assertFalse(Message.objects.exists())

    def test_members_cannot_read_other_members_conversations(self):
        self.send(self.groom_client, self.bride, "Private words")
        outsider = make_profile(gender="male")
        subscribe(outsider.user, "silver")
        client = client_for(outsider.user)
        self.assertEqual(client.get(MESSAGES).json()["count"], 0)
        # Asking for the bride's or the groom's conversation only ever gives the outsider's own (empty) one.
        for other in (self.bride, self.groom):
            response = client.get(self.thread(client, other))
            self.assertNotIn("Private words", response.content.decode())
        self.assertEqual(client.get(f"{MESSAGES}MM000000/").status_code, 404)
        self.assertEqual(client_for().get(MESSAGES).status_code, 401)

    def test_restricted_recipients_cannot_be_written_to(self):
        self.send(self.groom_client, self.bride, "Before")
        Profile.objects.filter(pk=self.bride.pk).update(visibility=Visibility.HIDDEN)
        response = self.send(self.groom_client, self.bride, "After")
        self.assertEqual((response.status_code, response.json()["code"]), (403, "unavailable"))
        # The groom still has his own history, without the option to write.
        thread = self.groom_client.get(self.thread(self.groom_client, self.bride)).json()
        self.assertEqual([m["body"] for m in thread["results"]], ["Before"])
        self.assertFalse(thread["messaging"]["can_send"])

        # A member who was never in a conversation and isn't visible is simply not found.
        suspended = make_profile(gender="female", status=ProfileStatus.SUSPENDED)
        self.assertEqual(self.send(self.groom_client, suspended).status_code, 404)

    def test_expired_starter_stops_and_the_other_member_may_still_reply(self):
        self.send(self.groom_client, self.bride)
        Subscription.objects.filter(pk=self.subscription.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.send(self.groom_client, self.bride).json()["code"], "upgrade_required")
        self.assertEqual(self.send(self.bride_client, self.groom, "Reply").status_code, 201)

    def test_unapproved_sender_and_invalid_messages(self):
        self.assertEqual(self.send(self.groom_client, self.bride, "   ").status_code, 400)
        self.assertEqual(self.send(self.groom_client, self.bride, "x" * 2001).status_code, 400)
        Profile.objects.filter(pk=self.groom.pk).update(status=ProfileStatus.PENDING_REVIEW)
        self.assertEqual(self.send(self.groom_client, self.bride).json()["code"], "profile_not_active")
        self.assertFalse(Message.objects.exists())

    def test_responses_carry_no_private_contact_details(self):
        self.send(self.groom_client, self.bride)
        for body in (self.bride_client.get(MESSAGES).json(),
                     self.bride_client.get(self.thread(self.bride_client, self.groom)).json()):
            keys = set(walk_keys(body))
            for private in PRIVATE_KEYS:
                if private != "id":  # a message's own id is public; no profile or user id is included
                    self.assertNotIn(private, keys)
            self.assertNotIn(self.groom.user.phone_number, str(body))
            self.assertNotIn(self.groom.user.email, str(body))

    def test_one_notification_per_batch_of_unread_messages(self):
        for text in ("One", "Two", "Three"):
            self.send(self.groom_client, self.bride, text)
        self.assertEqual(Notification.objects.filter(recipient=self.bride.user, kind="message_received").count(), 1)


class ProfileViewTests(TestCase):
    def setUp(self):
        self.owner = make_profile(gender="female")
        self.viewer = make_profile(gender="male", display_name="Arjun")
        self.owner_client = client_for(self.owner.user)
        self.viewer_client = client_for(self.viewer.user)
        self.detail = f"/api/v1/profiles/{self.owner.profile_code}/"

    def test_opening_a_profile_records_one_visit(self):
        for _ in range(3):  # reloads and repeated rendering
            self.assertEqual(self.viewer_client.get(self.detail).status_code, 200)
        view = ProfileView.objects.get()
        self.assertEqual((view.viewer, view.profile, view.visits), (self.viewer, self.owner, 1))
        ProfileView.objects.update(last_viewed_at=timezone.now() - VISIT_GAP - timedelta(seconds=1))
        self.viewer_client.get(self.detail)
        self.assertEqual(ProfileView.objects.get().visits, 2)

    def test_what_is_not_a_view(self):
        self.owner_client.get(self.detail)  # own profile
        client_for().get(self.detail)  # visitor
        self.viewer_client.get("/api/v1/profiles/search/")
        self.viewer_client.get("/api/v1/profiles/matches/")
        self.assertFalse(ProfileView.objects.exists())

    def test_silver_owner_sees_who_viewed(self):
        subscribe(self.owner.user, "silver")
        self.viewer_client.get(self.detail)
        body = self.owner_client.get(VIEWERS).json()
        self.assertEqual(body["count"], 1)
        item = body["results"][0]
        self.assertEqual((item["profile"]["profile_code"], item["visits"]), (self.viewer.profile_code, 1))
        keys = set(walk_keys(body))
        for private in PRIVATE_KEYS:
            self.assertNotIn(private, keys)

    def test_free_owner_gets_only_the_number(self):
        self.viewer_client.get(self.detail)
        response = self.owner_client.get(VIEWERS)
        self.assertEqual(response.status_code, 403)
        self.assertEqual((response.json()["code"], response.json()["viewer_count"]), ("upgrade_required", 1))
        self.assertNotIn(self.viewer.profile_code, response.content.decode())
        self.assertEqual(self.owner_client.get("/api/v1/dashboard/summary/").json()["profile_viewers"], 1)

    def test_the_list_is_only_ever_the_owners_own(self):
        subscribe(self.viewer.user, "silver")
        self.viewer_client.get(self.detail)
        # The viewer's own list: nobody viewed the viewer.
        self.assertEqual(self.viewer_client.get(VIEWERS).json()["count"], 0)
        self.assertEqual(client_for().get(VIEWERS).status_code, 401)

    def test_hidden_or_suspended_viewers_are_not_listed_and_photo_privacy_applies(self):
        subscribe(self.owner.user, "silver")
        self.viewer_client.get(self.detail)
        Profile.objects.filter(pk=self.viewer.pk).update(photo_visibility=PhotoVisibility.ACCEPTED)
        self.assertIsNone(self.owner_client.get(VIEWERS).json()["results"][0]["profile"]["photo"])
        for change in ({"visibility": Visibility.HIDDEN}, {"status": ProfileStatus.SUSPENDED}):
            with self.subTest(change=change):
                Profile.objects.filter(pk=self.viewer.pk).update(**change)
                self.assertEqual(self.owner_client.get(VIEWERS).json()["count"], 0)
                Profile.objects.filter(pk=self.viewer.pk).update(visibility=Visibility.MEMBERS, status=ProfileStatus.ACTIVE)
        self.assertEqual(ProfileView.objects.count(), 1)  # kept, just not listed

    def test_paginated(self):
        subscribe(self.owner.user, "silver")
        for _ in range(25):
            client_for(make_profile(gender="male").user).get(self.detail)
        first = self.owner_client.get(VIEWERS).json()
        second = self.owner_client.get(VIEWERS, {"page": 2}).json()
        self.assertEqual((first["count"], len(first["results"]), len(second["results"])), (25, 20, 5))


class SilverContactAllowanceTests(TestCase):
    """40 different members' numbers per Silver membership; viewing one again is free."""

    def setUp(self):
        self.groom = make_profile(gender="male")
        self.subscription = subscribe(self.groom.user, "silver")
        self.client = client_for(self.groom.user)
        self.brides = [make_profile(gender="female", contact_sharing="paid_members") for _ in range(41)]

    def view(self, profile):
        return self.client.post(f"/api/v1/profiles/{profile.profile_code}/contact/")

    def test_first_fortieth_and_forty_first(self):
        first = self.view(self.brides[0]).json()
        self.assertEqual((first["used"], first["limit"], first["phone_number"]), (1, 40, self.brides[0].user.phone_number))
        for bride in self.brides[1:39]:
            self.assertEqual(self.view(bride).status_code, 200)
        fortieth = self.view(self.brides[39]).json()
        self.assertEqual((fortieth["used"], fortieth["phone_number"]), (40, self.brides[39].user.phone_number))

        refused = self.view(self.brides[40])
        self.assertEqual((refused.status_code, refused.json()["code"]), (403, "limit_reached"))
        self.assertNotIn(self.brides[40].user.phone_number, refused.content.decode())
        # Numbers already viewed stay viewable at no cost.
        again = self.view(self.brides[0]).json()
        self.assertEqual((again["used"], again["phone_number"]), (40, self.brides[0].user.phone_number))

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.contact_views_used, 40)
        self.assertEqual(ContactView.objects.filter(subscription=self.subscription).count(), 40)
        remaining = self.client.get("/api/v1/memberships/me/").json()["entitlements"]["contact_views_remaining"]
        self.assertEqual(remaining, 0)

    def test_repeated_requests_count_once(self):
        for _ in range(5):
            self.assertEqual(self.view(self.brides[0]).status_code, 200)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.contact_views_used, 1)

    def test_denied_requests_use_nothing(self):
        Profile.objects.filter(pk=self.brides[0].pk).update(contact_sharing="hidden")
        groom = make_profile(gender="male", contact_sharing="paid_members")
        for profile, code in ((self.brides[0], "not_shared"), (groom, "same_gender"), (self.groom, "self")):
            with self.subTest(code=code):
                response = self.view(profile)
                self.assertEqual((response.status_code, response.json()["code"]), (403 if code != "self" else 409, code))
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.contact_views_used, 0)
        self.assertFalse(ContactView.objects.exists())

    def test_expired_silver_unlocks_nothing_new_and_keeps_the_history(self):
        self.view(self.brides[0])
        Subscription.objects.filter(pk=self.subscription.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
        for bride in self.brides[:2]:
            self.assertEqual(self.view(bride).json()["code"], "not_included")
        self.assertEqual(ContactView.objects.count(), 1)

    def test_numbers_never_appear_outside_the_contact_flow(self):
        self.view(self.brides[0])
        number = self.brides[0].user.phone_number
        for url in ("/api/v1/profiles/search/", "/api/v1/profiles/matches/", f"/api/v1/profiles/{self.brides[0].profile_code}/",
                    "/api/v1/dashboard/summary/"):
            with self.subTest(url=url):
                self.assertNotIn(number, self.client.get(url).content.decode())
        self.assertNotIn(number, client_for().get(f"/api/v1/profiles/{self.brides[0].profile_code}/").content.decode())


@unittest.skipUnless(connection.vendor == "mysql", "needs MySQL/MariaDB row locks")
class ConcurrentContactViewTests(TransactionTestCase):
    """Simultaneous requests from one member can't get past the allowance."""

    # Restore the seeded packages (and content types) for later tests, as ExistingDataMigrationTests does.
    serialized_rollback = True

    def test_simultaneous_unlocks_stop_at_the_limit(self):
        groom = make_profile(gender="male")
        subscription = subscribe(groom.user, "silver")
        brides = [make_profile(gender="female", contact_sharing="paid_members") for _ in range(6)]
        for bride in brides[:2]:
            services.view_contact(groom, bride.profile_code)
        Subscription.objects.filter(pk=subscription.pk).update(contact_views_used=39)  # one left

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

        threads = [threading.Thread(target=unlock, args=(bride,)) for bride in brides[2:]]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        subscription.refresh_from_db()
        self.assertEqual(sorted(results), ["limit_reached"] * 3 + ["ok"])
        self.assertEqual(subscription.contact_views_used, 40)
        self.assertEqual(ContactView.objects.filter(subscription=subscription).count(), 3)
