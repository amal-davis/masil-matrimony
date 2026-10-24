import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.memberships.models import MembershipPackage, Subscription
from apps.memberships.tests import subscribe
from apps.notifications.models import Notification, NotificationKind
from apps.profiles.choices import ProfileStatus, Visibility
from apps.profiles.models import Profile
from apps.profiles.test_utils import client_for, make_profile, make_user

from .models import ContactView, Interest, InterestStatus, Shortlist

SEND = "/api/v1/interests/"
RECEIVED = "/api/v1/interests/received/"
SENT = "/api/v1/interests/sent/"
SHORTLIST = "/api/v1/shortlist/"


def action_url(interest_id, action):
    return f"/api/v1/interests/{interest_id}/{action}/"


class InterestTests(TestCase):
    def setUp(self):
        self.groom = make_profile(gender="male", display_name="Arjun")
        self.bride = make_profile(gender="female", display_name="Meera")
        self.groom_client = client_for(self.groom.user)
        self.bride_client = client_for(self.bride.user)

    def send(self, client=None, code=None):
        return (client or self.groom_client).post(
            SEND, {"profile_code": code or self.bride.profile_code}, format="json"
        )

    def test_send_interest(self):
        response = self.send()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["status"], InterestStatus.PENDING)
        self.assertEqual(body["profile"]["profile_code"], self.bride.profile_code)
        self.assertTrue(Interest.objects.filter(sender=self.groom, receiver=self.bride).exists())

        notification = Notification.objects.get(recipient=self.bride.user)
        self.assertEqual(notification.kind, NotificationKind.INTEREST_RECEIVED)
        self.assertEqual(notification.link, "/dashboard/interests/received")

    def test_sender_profile_must_be_active(self):
        for status in [ProfileStatus.DRAFT, ProfileStatus.PENDING_REVIEW, ProfileStatus.REJECTED, ProfileStatus.SUSPENDED]:
            with self.subTest(status=status):
                Profile.objects.filter(pk=self.groom.pk).update(status=status)
                response = self.send()
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["code"], "profile_not_active")
        self.assertFalse(Interest.objects.exists())

    def test_member_without_profile(self):
        response = client_for(make_user()).post(SEND, {"profile_code": self.bride.profile_code}, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "no_profile")

    def test_duplicate(self):
        self.send()
        response = self.send()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "duplicate")
        self.assertEqual(Interest.objects.count(), 1)

    def test_reverse_pending_or_accepted(self):
        Interest.objects.create(sender=self.bride, receiver=self.groom)
        response = self.send()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "reverse_exists")

    def test_reverse_declined_allows_sending(self):
        Interest.objects.create(sender=self.bride, receiver=self.groom, status=InterestStatus.DECLINED)
        self.assertEqual(self.send().status_code, 201)

    def test_same_gender_and_self(self):
        other_groom = make_profile(gender="male")
        same = self.send(code=other_groom.profile_code)
        self.assertEqual(same.status_code, 409)
        self.assertEqual(same.json()["code"], "same_gender")
        self_send = self.send(code=self.groom.profile_code)
        self.assertEqual(self_send.status_code, 409)
        self.assertEqual(self_send.json()["code"], "self")

    def test_cannot_send_to_non_discoverable_profiles(self):
        hidden = make_profile(gender="female", visibility=Visibility.HIDDEN)
        draft = make_profile(gender="female", status=ProfileStatus.DRAFT)
        pending = make_profile(gender="female", status=ProfileStatus.PENDING_REVIEW)
        for profile in [hidden, draft, pending]:
            with self.subTest(status=profile.status, visibility=profile.visibility):
                self.assertEqual(self.send(code=profile.profile_code).status_code, 404)
        self.assertEqual(self.send(code="MM000000").status_code, 404)
        self.assertEqual(self.send(code="not a code!").status_code, 400)

    def test_accept(self):
        interest_id = self.send().json()["id"]
        response = self.bride_client.post(action_url(interest_id, "accept"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], InterestStatus.ACCEPTED)
        interest = Interest.objects.get(public_id=interest_id)
        self.assertEqual(interest.status, InterestStatus.ACCEPTED)
        self.assertIsNotNone(interest.responded_at)
        self.assertTrue(
            Notification.objects.filter(recipient=self.groom.user, kind=NotificationKind.INTEREST_ACCEPTED).exists()
        )

        # A second response, either way, is refused and changes nothing.
        for action in ["accept", "decline"]:
            again = self.bride_client.post(action_url(interest_id, action))
            self.assertEqual(again.status_code, 409)
            self.assertEqual(again.json()["code"], "not_pending")
        self.assertEqual(Interest.objects.get(public_id=interest_id).status, InterestStatus.ACCEPTED)

    def test_decline(self):
        interest_id = self.send().json()["id"]
        response = self.bride_client.post(action_url(interest_id, "decline"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Interest.objects.get(public_id=interest_id).status, InterestStatus.DECLINED)
        self.assertTrue(
            Notification.objects.filter(recipient=self.groom.user, kind=NotificationKind.INTEREST_DECLINED).exists()
        )
        # Can't re-send after being declined.
        resend = self.send()
        self.assertEqual(resend.status_code, 409)
        self.assertEqual(resend.json()["code"], "duplicate")

    def test_only_receiver_can_respond(self):
        interest_id = self.send().json()["id"]
        outsider = make_profile(gender="female")
        for client in [self.groom_client, client_for(outsider.user)]:
            for action in ["accept", "decline"]:
                self.assertEqual(client.post(action_url(interest_id, action)).status_code, 404)
        self.assertEqual(Interest.objects.get(public_id=interest_id).status, InterestStatus.PENDING)
        self.assertEqual(self.bride_client.post(action_url(uuid.uuid4(), "accept")).status_code, 404)

    def test_withdraw(self):
        interest_id = self.send().json()["id"]
        # Only the sender can withdraw.
        self.assertEqual(self.bride_client.post(action_url(interest_id, "withdraw")).status_code, 404)
        response = self.groom_client.post(action_url(interest_id, "withdraw"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Interest.objects.get(public_id=interest_id).status, InterestStatus.WITHDRAWN)

        # A withdrawn interest can't be withdrawn or answered again...
        self.assertEqual(self.groom_client.post(action_url(interest_id, "withdraw")).status_code, 409)
        self.assertEqual(self.bride_client.post(action_url(interest_id, "accept")).status_code, 409)
        # ...and is hidden from the receiver, but can be sent again.
        self.assertEqual(self.bride_client.get(RECEIVED).json()["count"], 0)
        resend = self.send()
        self.assertEqual(resend.status_code, 201)
        self.assertEqual(resend.json()["id"], interest_id)
        self.assertEqual(Interest.objects.get(public_id=interest_id).status, InterestStatus.PENDING)

    def test_cannot_withdraw_answered_interest(self):
        interest_id = self.send().json()["id"]
        self.bride_client.post(action_url(interest_id, "accept"))
        response = self.groom_client.post(action_url(interest_id, "withdraw"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Interest.objects.get(public_id=interest_id).status, InterestStatus.ACCEPTED)

    def test_lists_and_filters(self):
        other_brides = [make_profile(gender="female") for _ in range(3)]
        for bride in [self.bride, *other_brides]:
            self.send(code=bride.profile_code)
        Interest.objects.filter(receiver=other_brides[0]).update(status=InterestStatus.ACCEPTED)
        Interest.objects.filter(receiver=other_brides[1]).update(status=InterestStatus.DECLINED)

        sent = self.groom_client.get(SENT).json()
        self.assertTrue({"count", "next", "previous", "results"} <= set(sent))
        self.assertEqual(sent["count"], 4)
        self.assertEqual(self.groom_client.get(SENT, {"status": "accepted"}).json()["count"], 1)
        self.assertEqual(self.groom_client.get(SENT, {"status": "pending"}).json()["count"], 2)
        self.assertEqual(self.groom_client.get(SENT, {"status": "bogus"}).status_code, 400)

        received = self.bride_client.get(RECEIVED).json()
        self.assertEqual(received["count"], 1)
        item = received["results"][0]
        self.assertEqual(item["profile"]["profile_code"], self.groom.profile_code)
        self.assertTrue(item["profile"]["available"])
        self.assertNotIn("date_of_birth", item["profile"])
        # The groom received nothing.
        self.assertEqual(self.groom_client.get(RECEIVED).json()["count"], 0)

    def test_unavailable_profile_shows_stub(self):
        self.send()
        Profile.objects.filter(pk=self.groom.pk).update(visibility=Visibility.HIDDEN)
        item = self.bride_client.get(RECEIVED).json()["results"][0]
        self.assertFalse(item["profile"]["available"])
        self.assertEqual(set(item["profile"]), {"profile_code", "display_name", "available"})


class ShortlistTests(TestCase):
    def setUp(self):
        self.me = make_profile(gender="male")
        self.client = client_for(self.me.user)
        self.bride = make_profile(gender="female")

    def add(self, code):
        return self.client.post(SHORTLIST, {"profile_code": code}, format="json")

    def test_add_list_remove(self):
        self.assertEqual(self.add(self.bride.profile_code).status_code, 201)
        # Adding again is harmless.
        self.assertEqual(self.add(self.bride.profile_code).status_code, 201)
        self.assertEqual(Shortlist.objects.count(), 1)

        listing = self.client.get(SHORTLIST).json()
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["results"][0]["profile"]["profile_code"], self.bride.profile_code)

        self.assertEqual(self.client.delete(f"{SHORTLIST}{self.bride.profile_code}/").status_code, 204)
        self.assertEqual(self.client.get(SHORTLIST).json()["count"], 0)
        # Removing something not on the list is also harmless.
        self.assertEqual(self.client.delete(f"{SHORTLIST}{self.bride.profile_code}/").status_code, 204)

    def test_cannot_shortlist_self_or_hidden(self):
        self_add = self.add(self.me.profile_code)
        self.assertEqual(self_add.status_code, 409)
        hidden = make_profile(gender="female", visibility=Visibility.HIDDEN)
        draft = make_profile(gender="female", status=ProfileStatus.DRAFT)
        self.assertEqual(self.add(hidden.profile_code).status_code, 404)
        self.assertEqual(self.add(draft.profile_code).status_code, 404)
        self.assertFalse(Shortlist.objects.exists())

    def test_shortlists_are_private(self):
        self.add(self.bride.profile_code)
        other = client_for(make_profile(gender="male").user)
        self.assertEqual(other.get(SHORTLIST).json()["count"], 0)
        other.delete(f"{SHORTLIST}{self.bride.profile_code}/")
        self.assertEqual(Shortlist.objects.count(), 1)


class FreeInterestLimitTests(TestCase):
    """Free members may send 15 interests in total (one per member, no reset); paid members are unlimited."""

    def setUp(self):
        self.groom = make_profile(gender="male")
        self.client = client_for(self.groom.user)
        self.brides = [make_profile(gender="female") for _ in range(17)]

    def send(self, bride):
        return self.client.post(SEND, {"profile_code": bride.profile_code}, format="json")

    def test_sixteenth_interest_is_refused(self):
        for bride in self.brides[:15]:
            self.assertEqual(self.send(bride).status_code, 201)
        response = self.send(self.brides[15])
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "interest_limit_reached")
        self.assertEqual(Interest.objects.filter(sender=self.groom).count(), 15)
        self.assertEqual(
            self.client.get("/api/v1/memberships/me/").json()["entitlements"]["outgoing_interests_used"], 15
        )

    def test_withdrawing_does_not_free_a_slot_and_resending_is_not_counted_again(self):
        for bride in self.brides[:15]:
            self.send(bride)
        interest = Interest.objects.get(sender=self.groom, receiver=self.brides[0])
        self.client.post(action_url(interest.public_id, "withdraw"))
        self.assertEqual(self.send(self.brides[15]).status_code, 403)
        # The same member again: already counted, so it's allowed.
        self.assertEqual(self.send(self.brides[0]).status_code, 201)

    def test_paid_members_are_unlimited(self):
        subscribe(self.groom.user, "silver")
        for bride in self.brides:
            self.assertEqual(self.send(bride).status_code, 201)
        self.assertFalse(Interest.objects.filter(sender=self.groom, counts_toward_free_limit=True).exists())

    def test_interests_sent_while_paid_do_not_count_after_expiry(self):
        subscription = subscribe(self.groom.user, "silver")
        for bride in self.brides[:16]:
            self.send(bride)
        subscription.ends_at = timezone.now() - timedelta(seconds=1)
        subscription.save()
        self.assertEqual(self.send(self.brides[16]).status_code, 201)
        self.assertEqual(Interest.objects.filter(sender=self.groom, counts_toward_free_limit=True).count(), 1)

    def test_limit_comes_from_the_package(self):
        MembershipPackage.objects.filter(code="free").update(outgoing_interest_limit=2)
        self.assertEqual(self.send(self.brides[0]).status_code, 201)
        self.assertEqual(self.send(self.brides[1]).status_code, 201)
        self.assertEqual(self.send(self.brides[2]).status_code, 403)


class ContactNumberTests(TestCase):
    def setUp(self):
        self.groom = make_profile(gender="male")
        self.bride = make_profile(gender="female", contact_sharing="paid_members")
        self.client = client_for(self.groom.user)
        self.url = f"/api/v1/profiles/{self.bride.profile_code}/contact/"

    def test_free_member_gets_no_number(self):
        status = self.client.get(self.url).json()
        self.assertEqual(status["access"], "not_included")
        self.assertNotIn("phone_number", status)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "not_included")
        self.assertNotIn(self.bride.user.phone_number, response.content.decode())

    def test_assisted_packages_have_no_self_service_access(self):
        for code in ("platinum", "royal"):
            with self.subTest(plan=code):
                subscription = subscribe(self.groom.user, code)
                self.assertEqual(self.client.post(self.url).json()["code"], "not_included")
                subscription.delete()

    def test_paid_member_views_number_once_per_member(self):
        subscription = subscribe(self.groom.user, "silver")
        self.assertEqual(self.client.get(self.url).json()["access"], "available")
        body = self.client.post(self.url).json()
        self.assertEqual(body["phone_number"], self.bride.user.phone_number)
        self.assertEqual(body["used"], 1)
        self.assertEqual(body["limit"], 40)
        # Viewing the same member again doesn't use another view.
        body = self.client.post(self.url).json()
        self.assertEqual(body["used"], 1)
        subscription.refresh_from_db()
        self.assertEqual(subscription.contact_views_used, 1)
        self.assertEqual(ContactView.objects.filter(subscription=subscription).count(), 1)
        self.assertEqual(self.client.get(self.url).json()["access"], "viewed")

    def test_limit_reached(self):
        subscription = subscribe(self.groom.user, "silver")
        Subscription.objects.filter(pk=subscription.pk).update(contact_views_used=40)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "limit_reached")
        self.assertNotIn("phone_number", response.json())

    def test_requires_the_members_consent(self):
        subscribe(self.groom.user, "gold")
        Profile.objects.filter(pk=self.bride.pk).update(contact_sharing="hidden")
        self.assertEqual(self.client.post(self.url).json()["code"], "not_shared")
        self.assertFalse(ContactView.objects.exists())

    def test_withdrawn_consent_hides_a_number_already_viewed(self):
        subscribe(self.groom.user, "gold")
        self.assertEqual(self.client.post(self.url).status_code, 200)
        Profile.objects.filter(pk=self.bride.pk).update(contact_sharing="hidden")
        self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_expired_subscription_loses_access(self):
        subscription = subscribe(self.groom.user, "diamond")
        subscription.ends_at = timezone.now() - timedelta(seconds=1)
        subscription.save()
        self.assertEqual(self.client.post(self.url).json()["code"], "not_included")

    def test_new_subscription_has_its_own_count(self):
        old = subscribe(self.groom.user, "silver")
        self.client.post(self.url)
        old.ends_at = timezone.now() - timedelta(seconds=1)
        old.save()
        new = subscribe(self.groom.user, "gold")
        self.assertEqual(self.client.get(self.url).json()["access"], "available")
        self.assertEqual(self.client.post(self.url).json()["used"], 1)
        new.refresh_from_db()
        self.assertEqual(new.contact_views_used, 1)

    def test_hidden_or_own_profile(self):
        subscribe(self.groom.user, "silver")
        own = f"/api/v1/profiles/{self.groom.profile_code}/contact/"
        self.assertEqual(self.client.post(own).status_code, 409)
        Profile.objects.filter(pk=self.bride.pk).update(visibility=Visibility.HIDDEN)
        self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_unapproved_viewer(self):
        subscribe(self.groom.user, "silver")
        Profile.objects.filter(pk=self.groom.pk).update(status=ProfileStatus.PENDING_REVIEW)
        self.assertEqual(self.client.post(self.url).json()["code"], "profile_not_active")

    def test_signed_out(self):
        self.assertEqual(client_for().post(self.url).status_code, 401)

    def test_profile_detail_reports_status_without_number(self):
        subscribe(self.groom.user, "silver")
        response = self.client.get(f"/api/v1/profiles/{self.bride.profile_code}/")
        self.assertEqual(response.json()["viewer"]["contact"]["access"], "available")
        self.assertNotIn(self.bride.user.phone_number, response.content.decode())
