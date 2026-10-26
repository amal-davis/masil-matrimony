"""Partner-preference matchmaking (apps.profiles.matching) and GET /profiles/matches/."""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.accounts.roles import Role
from apps.interactions.models import Interest, InterestStatus, Shortlist

from . import matching, services
from .choices import PhotoStatus, PhotoVisibility, ProfileStatus, Visibility
from .models import PartnerPreference, Profile, default_must_haves
from .test_utils import TempMediaMixin, client_for, make_profile, make_user, upload
from .tests import walk_keys

MATCHES = "/api/v1/profiles/matches/"


def set_pref(profile, **values):
    pref = profile.partner_preference
    for name, value in values.items():
        setattr(pref, name, value)
    pref.save()
    return pref


class MatchingTestCase(TestCase):
    def setUp(self):
        self.user = make_user()
        self.me = make_profile(self.user, gender="male", age=30, religion="hindu", community="nair",
                               marital_status="never_married", mother_tongue="malayalam", city="Kochi",
                               district="Ernakulam", state="Kerala", height_cm=175)
        self.client = client_for(self.user)

    def get(self, **params):
        response = self.client.get(MATCHES, params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def codes(self, **params):
        return [item["profile_code"] for item in self.get(**params)["results"]]

    def card(self, profile):
        return next(item for item in self.get()["results"] if item["profile_code"] == profile.profile_code)


class EligibilityTests(MatchingTestCase):
    def test_candidate_meeting_every_must_have_is_shown(self):
        her = make_profile(gender="female", age=26, religion="hindu", marital_status="never_married")
        set_pref(self.me, age_min=24, age_max=28, religions=["hindu"], marital_statuses=["never_married"])
        self.assertEqual(self.codes(), [her.profile_code])

    def test_age_must_have_excludes_and_bounds_are_inclusive(self):
        at_min = make_profile(gender="female", age=24)
        at_max = make_profile(gender="female", age=28)
        make_profile(gender="female", age=23)
        make_profile(gender="female", age=29)
        set_pref(self.me, age_min=24, age_max=28)
        self.assertEqual(set(self.codes()), {at_min.profile_code, at_max.profile_code})

    def test_other_must_haves_exclude(self):
        nair = make_profile(gender="female", religion="hindu", community="nair", mother_tongue="malayalam")
        make_profile(gender="female", religion="hindu", community="ezhava", mother_tongue="malayalam")
        make_profile(gender="female", religion="hindu", community="nair", mother_tongue="tamil")
        set_pref(self.me, communities=["nair"], mother_tongues=["malayalam"], must_haves=["community", "mother_tongue"])
        self.assertEqual(self.codes(), [nair.profile_code])

    def test_text_must_have_matches_whole_words_only(self):
        kochi = make_profile(gender="female", city="Kochi", district="Ernakulam")
        native = make_profile(gender="female", city="Bengaluru", native_place="Thrissur")
        make_profile(gender="female", city="Kochiville", district="Palakkad")  # "kochi" only inside a word
        make_profile(gender="female", city="", district="", state="", country="", native_place="")
        set_pref(self.me, locations="kochi, Thrissur", must_haves=["location"])
        self.assertEqual(set(self.codes()), {kochi.profile_code, native.profile_code})

    def test_missing_data_never_meets_a_must_have(self):
        make_profile(gender="female", height_cm=None)
        tall = make_profile(gender="female", height_cm=165)
        set_pref(self.me, height_min_cm=150)
        self.assertEqual(self.codes(), [tall.profile_code])

    def test_unset_must_have_restricts_nothing(self):
        make_profile(gender="female", religion="christian", community="")
        make_profile(gender="female", religion="muslim", community="")
        set_pref(self.me, religions=[], must_haves=["religion"])
        self.assertEqual(len(self.codes()), 2)

    def test_own_profile_same_gender_and_undiscoverable_profiles_are_never_shown(self):
        visible = make_profile(gender="female")
        make_profile(gender="male")
        make_profile(gender="female", status=ProfileStatus.DRAFT)
        make_profile(gender="female", status=ProfileStatus.PENDING_REVIEW)
        make_profile(gender="female", status=ProfileStatus.SUSPENDED)
        make_profile(gender="female", visibility=Visibility.HIDDEN)
        inactive = make_profile(gender="female")
        inactive.user.is_active = False
        inactive.user.save()
        self.assertEqual(self.codes(), [visible.profile_code])
        self.assertNotIn(self.me.profile_code, self.codes())

    def test_no_eligible_profiles_gives_an_empty_list(self):
        make_profile(gender="female", age=40)
        set_pref(self.me, age_max=30)
        body = self.get()
        self.assertEqual((body["count"], body["results"]), (0, []))


class RankingTests(MatchingTestCase):
    def test_optional_preferences_rank_and_score(self):
        set_pref(self.me, age_min=None, age_max=None, religions=["hindu"], communities=["nair"],
                 locations="Kochi", education="B.Tech", occupation="Engineer", must_haves=[])
        best = make_profile(gender="female", religion="hindu", community="nair", city="Kochi",
                            highest_education="B.Tech", occupation="Software Engineer")
        middle = make_profile(gender="female", religion="hindu", community="ezhava", city="Kochi",
                              highest_education="MBA", occupation="Teacher")
        low = make_profile(gender="female", religion="christian", community="", city="Delhi",
                           highest_education="MBA", occupation="Doctor")
        self.assertEqual(self.codes(), [best.profile_code, middle.profile_code, low.profile_code])

        scores = {item["profile_code"]: item["match"]["score"] for item in self.get()["results"]}
        # religion 15 + community 10 + location 12 + education 8 + occupation 6 = 51 points configured.
        self.assertEqual(scores[best.profile_code], 100)
        self.assertEqual(scores[middle.profile_code], round(100 * (15 + 12) / 51))
        self.assertEqual(scores[low.profile_code], 0)

    def test_high_score_never_overrides_a_must_have(self):
        set_pref(self.me, age_min=24, age_max=28, religions=["hindu"], communities=["nair"], locations="Kochi",
                 must_haves=["age"])
        make_profile(gender="female", age=35, religion="hindu", community="nair", city="Kochi")  # perfect but too old
        weak = make_profile(gender="female", age=26, religion="christian", community="", city="Delhi")
        self.assertEqual(self.codes(), [weak.profile_code])

    def test_reasons_are_true_statements_about_the_members_preferences(self):
        set_pref(self.me, age_min=24, age_max=28, religions=["hindu"], height_min_cm=150, must_haves=["age"])
        her = make_profile(gender="female", age=26, religion="christian", community="", height_cm=None)
        match = self.card(her)["match"]
        self.assertEqual(match["reasons"], ["Matches your age preference (24–28)"])
        self.assertEqual(match["not_stated"], ["Height"])
        # 20 of 20 + 15 + 6 points.
        self.assertEqual(match["score"], round(100 * 20 / 41))

    def test_missing_candidate_data_earns_no_points(self):
        set_pref(self.me, education="B.Tech", must_haves=[])
        blank = make_profile(gender="female", highest_education="", education_detail="")
        match = self.card(blank)["match"]
        self.assertEqual((match["score"], match["reasons"], match["not_stated"]), (0, [], ["Education"]))

    def test_without_preferences_there_is_no_score_and_newest_approved_first(self):
        set_pref(self.me, must_haves=[])
        older = make_profile(gender="female")
        newer = make_profile(gender="female")
        Profile.objects.filter(pk=older.pk).update(reviewed_at="2026-01-01T00:00:00Z")
        Profile.objects.filter(pk=newer.pk).update(reviewed_at="2026-06-01T00:00:00Z")
        body = self.get()
        self.assertFalse(body["preferences_set"])
        self.assertEqual([item["profile_code"] for item in body["results"]], [newer.profile_code, older.profile_code])
        self.assertIsNone(body["results"][0]["match"]["score"])

    def test_database_and_python_rules_agree(self):
        set_pref(self.me, age_min=22, age_max=32, height_min_cm=155, height_max_cm=170, religions=["hindu"],
                 communities=["nair", "ezhava"], mother_tongues=["malayalam"], diets=["vegetarian"],
                 marital_statuses=["never_married"], locations="Kochi; Kerala", education="B.Tech/MBA",
                 occupation="engineer", must_haves=[])
        people = [
            make_profile(gender="female", age=25, height_cm=160, religion="hindu", community="nair", diet="vegetarian",
                         city="Kochi", highest_education="MBA", occupation="Engineer"),
            make_profile(gender="female", age=34, height_cm=180, religion="muslim", community="sunni",
                         mother_tongue="tamil", state="Tamil Nadu", highest_education="BA", occupation="Engineering"),
            make_profile(gender="female", age=22, height_cm=None, religion="hindu", community="ezhava",
                         marital_status="divorced", city="", district="", state="", country="", native_place=""),
        ]
        pref = matching.preference_of(Profile.objects.get(pk=self.me.pk))
        for criterion in matching.configured_criteria(pref):
            in_db = set(Profile.objects.filter(pk__in=[p.pk for p in people]).filter(criterion.q(pref)).values_list("pk", flat=True))
            in_python = {p.pk for p in people if criterion.test(pref, Profile.objects.get(pk=p.pk))}
            self.assertEqual(in_db, in_python, criterion.key)


class MutualTests(MatchingTestCase):
    def test_one_way_and_mutual_are_distinguished(self):
        set_pref(self.me, must_haves=[])
        likes_me = make_profile(gender="female")
        set_pref(likes_me, age_min=28, age_max=32, religions=["hindu"])  # I'm 30, Hindu
        wants_older = make_profile(gender="female")
        set_pref(wants_older, age_min=35)  # I'm too young for her
        no_requirements = make_profile(gender="female")
        set_pref(no_requirements, must_haves=[], religions=["christian"])  # a wish, not a requirement

        cards = {item["profile_code"]: item["match"]["mutual"] for item in self.get()["results"]}
        self.assertEqual(
            cards,
            {likes_me.profile_code: True, wants_older.profile_code: False, no_requirements.profile_code: True},
        )
        self.assertEqual(set(self.codes(mutual=1)), {likes_me.profile_code, no_requirements.profile_code})
        self.assertTrue(self.get(mutual=1)["mutual_only"])

    def test_their_preferences_are_never_returned(self):
        her = make_profile(gender="female")
        set_pref(her, age_min=28, age_max=32, locations="Secret Town", notes="private note")
        card = self.card(her)
        text = str(card)
        self.assertNotIn("Secret Town", text)
        self.assertNotIn("private note", text)
        self.assertFalse({"partner_preference", "partner_preferences", "must_haves"} & set(walk_keys(card)))


class PreferenceChangeTests(MatchingTestCase):
    def test_saving_preferences_changes_the_next_results(self):
        young = make_profile(gender="female", age=24, religion="hindu", community="nair")
        older = make_profile(gender="female", age=33, religion="christian", community="")
        self.assertEqual(set(self.codes()), {young.profile_code, older.profile_code})

        url = "/api/v1/profiles/me/partner-preference/"
        response = self.client.patch(url, {"age_max": 28}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.codes(), [young.profile_code])

        response = self.client.patch(url, {"must_haves": [], "religions": ["christian"], "age_max": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.codes(), [older.profile_code, young.profile_code])  # now only a ranking

    def test_preference_values_are_validated(self):
        url = "/api/v1/profiles/me/partner-preference/"
        for body, field in (
            ({"must_haves": ["salary"]}, "must_haves"),
            ({"mother_tongues": ["klingon"]}, "mother_tongues"),
            ({"diets": ["carnivore"]}, "diets"),
            ({"age_min": 30, "age_max": 25}, "age_max"),
            ({"age_min": 12}, "age_min"),
        ):
            with self.subTest(field=field):
                response = self.client.patch(url, body, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

    def test_new_and_existing_preferences_keep_the_previous_strict_criteria(self):
        self.assertEqual(self.me.partner_preference.must_haves, default_must_haves())
        self.assertEqual(PartnerPreference().must_haves, ["age", "height", "marital_status", "religion"])

    def test_profile_changes_apply_immediately(self):
        her = make_profile(gender="female", religion="hindu")
        set_pref(self.me, religions=["hindu"])
        self.assertEqual(self.codes(), [her.profile_code])
        her.religion, her.community = "christian", ""
        her.save()
        self.assertEqual(self.codes(), [])


class PaginationAndAccessTests(MatchingTestCase):
    def test_pages_have_no_duplicates_or_gaps(self):
        set_pref(self.me, religions=["hindu"], must_haves=[])
        for index in range(25):
            make_profile(gender="female", religion="hindu" if index % 2 else "christian", community="")
        first = self.get(page=1)
        second = self.get(page=2)
        codes = [item["profile_code"] for item in first["results"] + second["results"]]
        self.assertEqual(first["count"], 25)
        self.assertEqual(len(codes), 25)
        self.assertEqual(len(set(codes)), 25)
        scores = [item["match"]["score"] for item in first["results"] + second["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_requires_a_signed_in_member_with_a_profile(self):
        self.assertEqual(client_for().get(MATCHES).status_code, 401)
        self.assertEqual(client_for(make_user()).get(MATCHES).json()["code"], "no_profile")
        staff = make_user(role=Role.ADMIN)
        self.assertEqual(client_for(staff).get(MATCHES).status_code, 403)

    def test_results_are_always_for_the_signed_in_member(self):
        other = make_profile(gender="female", age=25)
        set_pref(other, age_min=60)  # would match nobody
        candidate = make_profile(gender="female")
        # Query parameters can't select someone else's matches.
        codes = self.codes(profile=other.profile_code, user=other.user.public_id)
        self.assertIn(candidate.profile_code, codes)
        self.assertIn(other.profile_code, codes)

    def test_cards_hold_no_contact_details_or_private_fields(self):
        her = make_profile(gender="female", annual_income="10l_20l", income_visible=False)
        card = self.card(her)
        self.assertFalse(
            {"date_of_birth", "email", "phone_number", "annual_income", "contact", "contact_sharing"} & set(walk_keys(card))
        )
        self.assertNotIn(her.user.phone_number, str(card))

    def test_query_count_does_not_grow_with_the_number_of_matches(self):
        set_pref(self.me, religions=["hindu"], locations="Kochi", must_haves=[])
        for _ in range(3):
            make_profile(gender="female", religion="hindu", city="Kochi")

        def count_queries():
            with CaptureQueriesContext(connection) as queries:
                self.get()
            return len(queries)

        few = count_queries()
        for _ in range(9):
            make_profile(gender="female", religion="hindu", city="Kochi")
        self.assertEqual(count_queries(), few)


class PhotoPrivacyTests(TempMediaMixin, MatchingTestCase):
    def test_photo_privacy_is_respected_in_matches(self):
        open_photos = make_profile(gender="female")
        services.add_photo(open_photos, upload())
        open_photos.photos.update(status=PhotoStatus.APPROVED)
        private = make_profile(gender="female", photo_visibility=PhotoVisibility.ACCEPTED)
        services.add_photo(private, upload())
        private.photos.update(status=PhotoStatus.APPROVED)

        self.assertIsNotNone(self.card(open_photos)["photo"])
        card = self.card(private)
        self.assertIsNone(card["photo"])
        self.assertTrue(card["photos_hidden"])

        Interest.objects.create(sender=self.me, receiver=private, status=InterestStatus.ACCEPTED)
        card = self.card(private)
        self.assertIsNotNone(card["photo"])
        self.assertFalse(card["photos_hidden"])

    def test_shortlist_flag(self):
        her = make_profile(gender="female")
        Shortlist.objects.create(owner=self.me, profile=her)
        self.assertTrue(self.card(her)["shortlisted"])
