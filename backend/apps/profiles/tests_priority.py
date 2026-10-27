"""Priority Profile Visibility (apps.profiles.priority): its real effect on search and match order."""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.memberships.models import Subscription
from apps.memberships.tests import subscribe

from .choices import ProfileStatus, Visibility
from .models import PartnerPreference
from .test_utils import client_for, make_profile

SEARCH = "/api/v1/profiles/search/"
MATCHES = "/api/v1/profiles/matches/"


class PriorityTestCase(TestCase):
    def setUp(self):
        self.me = make_profile(gender="male", age=30)
        self.client = client_for(self.me.user)
        # Created oldest first, so without priority the order is newest first: c, b, a.
        self.a = make_profile(gender="female", display_name="A")
        self.b = make_profile(gender="female", display_name="B")
        self.c = make_profile(gender="female", display_name="C")

    def codes(self, url=SEARCH, **params):
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200, response.content)
        return [item["profile_code"] for item in response.json()["results"]]


class SearchPriorityTests(PriorityTestCase):
    def test_gold_and_diamond_profiles_come_first_within_the_results(self):
        self.assertEqual(self.codes(), [self.c.profile_code, self.b.profile_code, self.a.profile_code])
        subscribe(self.a.user, "gold")
        self.assertEqual(self.codes(), [self.a.profile_code, self.c.profile_code, self.b.profile_code])
        subscribe(self.b.user, "diamond")
        self.assertEqual(self.codes(), [self.b.profile_code, self.a.profile_code, self.c.profile_code])

    def test_silver_and_assisted_packages_get_no_boost(self):
        subscribe(self.a.user, "silver")
        subscribe(self.b.user, "platinum")
        self.assertEqual(self.codes(), [self.c.profile_code, self.b.profile_code, self.a.profile_code])

    def test_priority_never_bypasses_filters_or_eligibility(self):
        for profile in (self.a, self.b):
            subscribe(profile.user, "gold")
        type(self.a).objects.filter(pk=self.a.pk).update(religion="christian", community="")
        type(self.b).objects.filter(pk=self.b.pk).update(visibility=Visibility.HIDDEN)
        suspended = make_profile(gender="female", status=ProfileStatus.SUSPENDED)
        subscribe(suspended.user, "gold")
        groom = make_profile(gender="male")
        subscribe(groom.user, "gold")
        self.assertEqual(self.codes(religion="hindu"), [self.c.profile_code])
        self.assertNotIn(groom.profile_code, self.codes())

    def test_expired_gold_loses_the_boost(self):
        subscription = subscribe(self.a.user, "gold")
        Subscription.objects.filter(pk=subscription.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.codes()[-1], self.a.profile_code)

    @override_settings(PRIORITY_VISIBILITY_ENABLED=False)
    def test_switched_off_means_the_usual_order(self):
        subscribe(self.a.user, "gold")
        self.assertEqual(self.codes(), [self.c.profile_code, self.b.profile_code, self.a.profile_code])

    def test_the_searchers_own_package_changes_nothing(self):
        subscribe(self.me.user, "gold")
        self.assertEqual(self.codes(), [self.c.profile_code, self.b.profile_code, self.a.profile_code])


class MatchPriorityTests(PriorityTestCase):
    def test_priority_orders_equal_matches_only(self):
        PartnerPreference.objects.update_or_create(profile=self.me, defaults={"religions": ["hindu"], "must_haves": []})
        type(self.c).objects.filter(pk=self.c.pk).update(religion="christian", community="")
        subscribe(self.c.user, "gold")  # a weaker match: Gold can't lift it above better ones
        subscribe(self.a.user, "gold")
        self.assertEqual(self.codes(MATCHES), [self.a.profile_code, self.b.profile_code, self.c.profile_code])

    def test_without_preferences_priority_comes_first(self):
        subscribe(self.a.user, "gold")
        self.assertEqual(self.codes(MATCHES), [self.a.profile_code, self.c.profile_code, self.b.profile_code])
