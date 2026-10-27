"""
Automatic matchmaking (apps.matchmaking): the stored recommendations, both
directions, mutual compatibility, review, staleness, the admin pages, the
command and the member's protected view. Scoring itself is
apps.profiles.matching's (tests_matching.py); these check it is used as is.
"""
from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.roles import Role
from apps.interactions.models import Interest, InterestStatus
from apps.profiles.choices import ProfileStatus, Visibility
from apps.profiles.models import PartnerPreference, Profile
from apps.profiles.test_utils import client_for, make_profile, make_user

from . import engine
from .models import MatchPair, MatchRecommendation, MatchRun, RecommendationStatus, ReviewEvent, ReviewStatus

MATCHES = "/api/v1/profiles/matches/"


def prefs(profile, **values):
    """Replace the member's preferences with exactly these (anything not given is unspecified)."""
    values.setdefault("must_haves", [])
    PartnerPreference.objects.filter(profile=profile).delete()
    PartnerPreference.objects.create(profile=profile, **values)


def pair_of(a, b):
    return MatchPair.objects.get(profile_low=min(a.pk, b.pk), profile_high=max(a.pk, b.pk))


def age_years_ago(years):
    today = date.today()
    return date(today.year - years, 1, 1)


def staff(*codenames):
    user = make_user(Role.ADMIN, is_staff=True)
    user.user_permissions.add(*Permission.objects.filter(content_type__app_label="matchmaking", codename__in=codenames))
    return type(user).objects.get(pk=user.pk)


class MatchTestCase(TestCase):
    def setUp(self):
        self.groom = make_profile(gender="male", display_name="Arjun", age=30)
        self.bride = make_profile(gender="female", display_name="Meera", age=26)
        self.bride2 = make_profile(gender="female", display_name="Diya", age=27, religion="christian", community="")

    def rec(self, member, candidate):
        return MatchRecommendation.objects.filter(member=member, candidate=candidate).first()


class EngineTests(MatchTestCase):
    def test_required_preferences_filter_and_optional_ones_score(self):
        prefs(self.groom, religions=["hindu"], must_haves=["religion"], age_min=24, age_max=28)
        engine.generate_for(self.groom)
        self.assertIsNotNone(self.rec(self.groom, self.bride))
        self.assertIsNone(self.rec(self.groom, self.bride2))  # required religion not met: never stored
        rec = self.rec(self.groom, self.bride)
        self.assertEqual(rec.score, 100)
        self.assertEqual(rec.reasons, ["Matches your age preference (24–28)", "Matches your religion preference"])

        prefs(self.groom, religions=["hindu"], must_haves=[], age_min=24, age_max=28)
        engine.generate_for(self.groom)
        other = self.rec(self.groom, self.bride2)  # optional now: a lower score, with what wasn't met
        self.assertEqual((other.score, other.mismatched), (57, ["Religion"]))  # age 20 of 35 points

    def test_age_and_height_boundaries_and_unspecified_and_missing_data(self):
        Profile.objects.filter(pk=self.bride.pk).update(date_of_birth=age_years_ago(28), height_cm=160)
        Profile.objects.filter(pk=self.bride2.pk).update(date_of_birth=age_years_ago(29), height_cm=None)
        prefs(self.groom, age_min=24, age_max=28, height_min_cm=160, height_max_cm=170)
        engine.generate_for(self.groom)
        at_edge = self.rec(self.groom, self.bride)
        self.assertEqual(at_edge.score, 100)  # 28 and 160 cm are inside the ranges
        outside = self.rec(self.groom, self.bride2)
        self.assertEqual(outside.score, 0)
        self.assertEqual((outside.mismatched, outside.not_stated), (["Age"], ["Height"]))  # missing data never counts

        # Unspecified preferences aren't mismatches: only the filled-in criteria are scored.
        prefs(self.groom, age_min=24, age_max=28)
        engine.generate_for(self.groom)
        self.assertEqual((self.rec(self.groom, self.bride2).mismatched, self.rec(self.groom, self.bride2).not_stated),
                         (["Age"], []))

    def test_a_required_preference_without_data_excludes(self):
        Profile.objects.filter(pk=self.bride.pk).update(height_cm=None)
        prefs(self.groom, height_min_cm=150, must_haves=["height"])
        engine.generate_for(self.groom)
        self.assertIsNone(self.rec(self.groom, self.bride))

    def test_ineligible_profiles_and_self_are_never_recommended(self):
        hidden = make_profile(gender="female", visibility=Visibility.HIDDEN)
        suspended = make_profile(gender="female", status=ProfileStatus.SUSPENDED)
        pending = make_profile(gender="female", status=ProfileStatus.PENDING_REVIEW)
        inactive = make_profile(gender="female")
        type(inactive.user).objects.filter(pk=inactive.user_id).update(is_active=False)
        groom2 = make_profile(gender="male")
        prefs(self.groom, age_min=18)
        engine.generate_for(self.groom)
        found = set(MatchRecommendation.objects.filter(member=self.groom).values_list("candidate_id", flat=True))
        self.assertEqual(found, {self.bride.pk, self.bride2.pk})
        self.assertFalse(found & {hidden.pk, suspended.pk, pending.pk, inactive.pk, groom2.pk, self.groom.pk})

    def test_no_preferences_no_recommendations(self):
        engine.generate_for(self.groom)
        self.assertFalse(MatchRecommendation.objects.exists())
        self.assertIn(self.groom, engine.incomplete_preference_members())


class DirectionAndMutualTests(MatchTestCase):
    def test_each_direction_is_its_own_evaluation_and_mutual_needs_both(self):
        prefs(self.groom, age_min=24, age_max=28)
        prefs(self.bride, age_min=35, must_haves=["age"])  # the groom (30) doesn't suit her
        engine.generate_for(self.groom)
        forward = self.rec(self.groom, self.bride)
        self.assertEqual(forward.status, RecommendationStatus.ACTIVE)
        self.assertFalse(forward.reverse_must_haves_met)
        self.assertIsNone(self.rec(self.bride, self.groom))  # one-sided
        pair = pair_of(self.groom, self.bride)
        self.assertEqual((pair.profile_low_id < pair.profile_high_id, pair.mutual), (True, False))

        prefs(self.bride, age_min=28, age_max=32, must_haves=["age"], religions=["christian"])
        engine.generate_for(self.groom)  # one member's run evaluates the reverse direction too
        backward = self.rec(self.bride, self.groom)
        self.assertEqual(backward.status, RecommendationStatus.ACTIVE)
        self.assertNotEqual(backward.score, forward.score)  # each from its own member's preferences (50 vs 100)
        pair.refresh_from_db()
        self.assertTrue(pair.mutual)
        self.assertIsNotNone(pair.mutual_since)
        # One record per unordered pair, however many times either member is evaluated.
        engine.generate_for(self.bride)
        engine.generate_for(self.groom)
        self.assertEqual(MatchPair.objects.filter(profile_low=min(self.groom.pk, self.bride.pk),
                                                  profile_high=max(self.groom.pk, self.bride.pk)).count(), 1)
        self.assertEqual(MatchPair.objects.count(), 2)  # groom-bride and groom-bride2

    def test_mutual_interest_is_not_compatibility(self):
        prefs(self.groom, age_min=24, age_max=28)
        prefs(self.bride2, age_min=40, must_haves=["age"])
        Interest.objects.create(sender=self.groom, receiver=self.bride2)
        Interest.objects.create(sender=self.bride2, receiver=self.groom)
        engine.generate_for(self.groom)
        pair = pair_of(self.groom, self.bride2)
        self.assertFalse(pair.mutual)  # both sent interests, but he doesn't meet her must-haves
        from .admin import interest_state

        self.assertEqual(interest_state(self.groom, self.bride2), "Mutual interest (both sent)")
        Interest.objects.filter(sender=self.groom).update(status=InterestStatus.ACCEPTED)
        self.assertEqual(interest_state(self.groom, self.bride2), "Interest accepted")


class LifecycleTests(MatchTestCase):
    def test_idempotent_and_stable(self):
        prefs(self.groom, age_min=24, age_max=28)
        first = engine.generate_for(self.groom)
        order = list(MatchRecommendation.objects.filter(member=self.groom).order_by("-score", "candidate_id")
                     .values_list("candidate_id", "score"))
        second = engine.generate_for(self.groom)
        self.assertEqual((first.created, second.created, second.updated, second.unchanged), (2, 0, 0, 2))
        self.assertEqual(MatchRecommendation.objects.filter(member=self.groom).count(), 2)
        self.assertEqual(list(MatchRecommendation.objects.filter(member=self.groom).order_by("-score", "candidate_id")
                              .values_list("candidate_id", "score")), order)

    def test_changes_mark_stale_and_regenerate(self):
        prefs(self.groom, age_min=24, age_max=28)
        engine.generate_for(self.groom)
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            prefs(self.groom, age_min=24, age_max=26)  # the member's preferences changed
        self.assertTrue(MatchRecommendation.objects.filter(member=self.groom, status="stale").exists())
        for callback in callbacks:
            callback()  # the regeneration that runs after the save is committed
        self.assertEqual(self.rec(self.groom, self.bride).status, RecommendationStatus.ACTIVE)
        withdrawn = self.rec(self.groom, self.bride2)  # 27 is now outside: kept, marked, not deleted
        self.assertEqual(withdrawn.score, 0)

        # A candidate's relevant change marks recommendations of them stale; others don't.
        self.bride.occupation = "Doctor"
        self.bride.save()
        self.assertEqual(self.rec(self.groom, self.bride).status, RecommendationStatus.STALE)
        self.bride2.save(update_fields=["updated_at"])
        self.assertEqual(self.rec(self.groom, self.bride2).status, RecommendationStatus.ACTIVE)

    def test_no_longer_eligible_is_kept_not_deleted(self):
        prefs(self.groom, age_min=24, age_max=28)
        engine.generate_for(self.groom)
        Profile.objects.filter(pk=self.bride.pk).update(visibility=Visibility.HIDDEN)
        result = engine.generate_for(self.groom)
        self.assertEqual(result.withdrawn, 1)
        self.assertEqual(self.rec(self.groom, self.bride).status, RecommendationStatus.INELIGIBLE)

    @override_settings(MATCH_REVIEW_REQUIRED=True)
    def test_review_decisions_survive_unchanged_runs_and_requeue_after_changes(self):
        prefs(self.groom, age_min=24, age_max=28)
        engine.generate_for(self.groom)
        rec, dismissed = self.rec(self.groom, self.bride), self.rec(self.groom, self.bride2)
        self.assertEqual(rec.review_status, ReviewStatus.PENDING)
        reviewer = staff("review_matchrecommendation")
        engine.review([rec], reviewer, ReviewStatus.APPROVED)
        engine.review([dismissed], reviewer, ReviewStatus.DISMISSED, "Family requested no matches from Kochi.")
        engine.generate_for(self.groom)
        rec.refresh_from_db()
        self.assertEqual((rec.review_status, rec.reviewed_by), (ReviewStatus.APPROVED, reviewer))

        Profile.objects.filter(pk=self.bride.pk).update(occupation="Architect")
        Profile.objects.filter(pk=self.bride2.pk).update(occupation="Architect")
        engine.generate_for(self.groom)
        rec.refresh_from_db()
        dismissed.refresh_from_db()
        self.assertEqual(rec.review_status, ReviewStatus.PENDING)  # data changed: back to review
        self.assertEqual(dismissed.review_status, ReviewStatus.DISMISSED)  # dismissals stay
        self.assertEqual(list(rec.review_events.values_list("review_status", flat=True)), ["approved", "pending"])
        with self.assertRaises(ValueError):
            engine.review([rec], reviewer, ReviewStatus.DISMISSED, "")  # a reason is required

    @override_settings(MATCH_RECOMMENDATION_LIMIT=1)
    def test_limit(self):
        prefs(self.groom, age_min=18)
        engine.generate_for(self.groom)
        self.assertEqual(MatchRecommendation.objects.filter(member=self.groom).count(), 1)

    def test_command_and_runs(self):
        prefs(self.groom, age_min=24, age_max=28)
        out = StringIO()
        call_command("generate_matches", stdout=out)
        self.assertIn("2 new", out.getvalue())
        call_command("generate_matches", "--all", stdout=StringIO())
        self.assertEqual(MatchRecommendation.objects.filter(member=self.groom).count(), 2)
        call_command("generate_matches", "--member", self.groom.profile_code.lower(), stdout=StringIO())
        self.assertEqual(MatchRun.objects.count(), 3)
        self.assertEqual(MatchRun.objects.first().unchanged, 2)


class MemberViewTests(MatchTestCase):
    def setUp(self):
        super().setUp()
        prefs(self.groom, age_min=24, age_max=28)
        engine.generate_for(self.groom)
        self.client = client_for(self.groom.user)

    def codes(self):
        return [item["profile_code"] for item in self.client.get(MATCHES).json()["results"]]

    def test_hidden_and_dismissed_are_left_out_and_nothing_private_is_returned(self):
        self.assertEqual(set(self.codes()), {self.bride.profile_code, self.bride2.profile_code})
        self.assertEqual(self.client.post(f"{MATCHES}{self.bride.profile_code}/hide/").status_code, 204)
        self.assertEqual(self.codes(), [self.bride2.profile_code])
        engine.review([self.rec(self.groom, self.bride2)], staff(), ReviewStatus.DISMISSED, "Not suitable.")
        self.assertEqual(self.codes(), [])
        # The bride's own list is unaffected by the groom hiding her.
        prefs(self.bride, age_min=25)
        self.assertIn(self.groom.profile_code, [i["profile_code"] for i in client_for(self.bride.user).get(MATCHES).json()["results"]])

    def test_response_has_no_admin_metadata_or_contact_details(self):
        text = self.client.get(MATCHES).content.decode()
        for private in ("review_status", "mismatched", "reverse_must_haves", "fingerprint", self.bride.user.phone_number,
                        self.bride.user.email):
            self.assertNotIn(private, text)

    @override_settings(MATCH_REVIEW_REQUIRED=True)
    def test_with_review_required_only_approved_are_shown(self):
        self.assertEqual(self.codes(), [])  # published automatically before: not approved
        engine.review([self.rec(self.groom, self.bride)], staff(), ReviewStatus.APPROVED)
        self.assertEqual(self.codes(), [self.bride.profile_code])

    def test_hide_only_affects_own_list_and_only_visible_profiles(self):
        hidden = make_profile(gender="female", visibility=Visibility.HIDDEN)
        self.assertEqual(self.client.post(f"{MATCHES}{hidden.profile_code}/hide/").status_code, 404)
        self.assertEqual(self.client.post(f"{MATCHES}{self.groom.profile_code}/hide/").status_code, 404)
        self.assertEqual(client_for().post(f"{MATCHES}{self.bride.profile_code}/hide/").status_code, 401)


class AdminTests(MatchTestCase):
    def setUp(self):
        super().setUp()
        prefs(self.groom, age_min=24, age_max=28)
        engine.generate_for(self.groom)
        self.list_url = reverse("admin:matchmaking_matchrecommendation_changelist")

    def browser(self, user):
        client = Client()
        client.force_login(user)
        return client

    def test_permissions(self):
        self.assertEqual(self.browser(staff()).get(self.list_url).status_code, 403)
        viewer = self.browser(staff("view_matchrecommendation"))
        self.assertEqual(viewer.get(self.list_url).status_code, 200)
        self.assertEqual(viewer.get(reverse("admin:matchmaking_analytics")).status_code, 200)
        self.assertEqual(viewer.get(reverse("admin:matchmaking_generate")).status_code, 403)
        rec = self.rec(self.groom, self.bride)
        viewer.post(self.list_url, {"action": "approve", "_selected_action": [rec.pk]})
        rec.refresh_from_db()
        self.assertEqual(rec.review_status, ReviewStatus.NOT_REQUIRED)  # no review permission: nothing happened
        self.assertNotEqual(self.browser(self.groom.user).get(self.list_url).status_code, 200)

    def test_list_detail_and_query_efficiency(self):
        superuser = make_user(Role.SUPER_ADMIN, is_staff=True, is_superuser=True)
        browser = self.browser(superuser)
        rec = self.rec(self.groom, self.bride)
        page = browser.get(reverse("admin:matchmaking_matchrecommendation_change", args=[rec.pk]))
        self.assertContains(page, "Matches your age preference")
        self.assertContains(page, "No interest yet")

        def queries():
            with CaptureQueriesContext(connection) as context:
                self.assertEqual(browser.get(self.list_url).status_code, 200)
            return len(context.captured_queries)

        few = queries()
        for _ in range(5):
            make_profile(gender="female", age=25)
        engine.generate_for(self.groom)
        self.assertEqual(queries(), few)

    def test_review_actions_record_who_and_why(self):
        reviewer = staff("view_matchrecommendation", "review_matchrecommendation")
        browser = self.browser(reviewer)
        rec = self.rec(self.groom, self.bride)
        confirm = browser.post(self.list_url, {"action": "dismiss", "_selected_action": [rec.pk]})
        self.assertContains(confirm, "Reason")  # a confirmation step first
        rec.refresh_from_db()
        self.assertEqual(rec.review_status, ReviewStatus.NOT_REQUIRED)
        browser.post(self.list_url, {"action": "dismiss", "_selected_action": [rec.pk], "confirmed": "yes",
                                     "reason": "Already introduced offline."})
        rec.refresh_from_db()
        self.assertEqual((rec.review_status, rec.reviewed_by, rec.review_note),
                         (ReviewStatus.DISMISSED, reviewer, "Already introduced offline."))
        self.assertEqual(ReviewEvent.objects.get().staff, reviewer)

    def test_generate_needs_permission_and_confirmation_for_everyone(self):
        generator = self.browser(staff("view_matchrecommendation", "generate_matchrecommendation"))
        url = reverse("admin:matchmaking_generate")
        before = MatchRun.objects.count()
        generator.post(url, {"scope": "all"})  # not confirmed
        self.assertEqual(MatchRun.objects.count(), before)
        generator.post(url, {"scope": "all", "confirm_all": "yes"})
        self.assertEqual(MatchRun.objects.count(), before + 1)
        generator.post(url, {"scope": "ids", "codes": f"{self.groom.profile_code}"})
        self.assertEqual(MatchRun.objects.first().members_evaluated, 1)

    def test_queue_mutual_list_and_analytics(self):
        superuser = self.browser(make_user(Role.SUPER_ADMIN, is_staff=True, is_superuser=True))
        with override_settings(MATCH_REVIEW_REQUIRED=True):
            Profile.objects.filter(pk=self.bride.pk).update(occupation="Teacher")
            engine.generate_for(self.groom)
            queue = superuser.get(reverse("admin:matchmaking_pendingrecommendation_changelist"))
            self.assertEqual([r.candidate_id for r in queue.context["cl"].result_list], [self.bride.pk])
        prefs(self.bride, age_min=28, age_max=32)
        engine.generate_for(self.bride)
        mutual = superuser.get(reverse("admin:matchmaking_mutualmatch_changelist"))
        self.assertEqual(len(mutual.context["cl"].result_list), 1)
        figures = engine.analytics(start=None, end=None)
        self.assertEqual((figures["mutual"], figures["members"], figures["current"]), (1, 2, 3))
        self.assertEqual(figures["incomplete"], 1)  # bride2 has no preferences
        page = superuser.get(reverse("admin:matchmaking_analytics"), {"from": str(date.today() - timedelta(days=1)),
                                                                      "to": str(date.today())})
        self.assertEqual(page.context["figures"]["in_period"], 3)
