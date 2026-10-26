"""Profile search (apps.profiles.search) and GET /profiles/search/."""
from datetime import date, timedelta
from unittest import mock

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.roles import Role

from .choices import ProfileStatus, Visibility
from .models import Profile
from .test_utils import COMPLETE_FIELDS, client_for, make_profile, make_user
from .tests import walk_keys

SEARCH = "/api/v1/profiles/search/"


class SearchTestCase(TestCase):
    def setUp(self):
        self.user = make_user()
        self.me = make_profile(self.user, gender="male", age=30)
        self.client = client_for(self.user)

    def get(self, expect=200, **params):
        response = self.client.get(SEARCH, params)
        self.assertEqual(response.status_code, expect, response.content)
        return response.json()

    def codes(self, **params):
        return [item["profile_code"] for item in self.get(**params)["results"]]

    def bride(self, **fields):
        return make_profile(gender="female", **fields)


class FindingProfilesTests(SearchTestCase):
    def test_a_newly_registered_and_approved_profile_can_be_found(self):
        """Through the real flow: create the profile, submit it, staff approve it."""
        user = make_user()
        member = client_for(user)
        created = member.post("/api/v1/profiles/me/", {
            "created_for": "self", "display_name": "Anu", "gender": "female",
            "date_of_birth": "1998-05-04", **COMPLETE_FIELDS,
        }, format="json")
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)
        code = created.json()["profile_code"]
        self.assertNotIn(code, self.codes())  # a draft isn't searchable

        self.assertEqual(member.post("/api/v1/profiles/me/submit/").status_code, 200)
        self.assertNotIn(code, self.codes())  # nor one awaiting review

        root = make_user(role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True)
        self.client.force_login(root)
        profile = Profile.objects.get(profile_code=code)
        self.client.post(reverse("admin:profiles_profile_changelist"), {"action": "approve", "_selected_action": [profile.pk]})
        profile.refresh_from_db()
        self.assertEqual(profile.status, ProfileStatus.ACTIVE)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.codes(religion="hindu", location="thrissur", profile_id=code.lower()), [code])

    def test_empty_filters_return_every_eligible_profile(self):
        a, b = self.bride(), self.bride()
        self.assertEqual(sorted(self.codes()), sorted([a.profile_code, b.profile_code]))
        self.assertEqual(sorted(self.codes(religion="", age_min="", location="")), sorted([a.profile_code, b.profile_code]))

    def test_each_filter_includes_matches_and_excludes_the_rest(self):
        cases = [
            ({"religion": "christian"}, {"religion": "christian", "community": "syro-malabar"}, {"religion": "hindu"}),
            ({"religion": "christian", "caste": "marthoma"}, {"religion": "christian", "community": "marthoma"},
             {"religion": "christian", "community": "jacobite"}),
            ({"marital_status": "divorced"}, {"marital_status": "divorced"}, {"marital_status": "never_married"}),
            ({"mother_tongue": "tamil"}, {"mother_tongue": "tamil"}, {"mother_tongue": "malayalam"}),
            ({"height_min": 160, "height_max": 170}, {"height_cm": 165}, {"height_cm": 172}),
            ({"location": "kottayam"}, {"district": "Kottayam"}, {"district": "Thrissur"}),
            ({"location": "kottayam"}, {"district": "", "city": "kottayam"}, {"district": "", "city": "Kochi"}),
            ({"location": "rest-of-india"}, {"state": "Karnataka", "district": "Bengaluru"}, {"state": "Kerala"}),
            ({"location": "abroad"}, {"country": "UAE", "state": "Dubai", "district": ""}, {"country": "India"}),
            ({"education": "  m.tech  "}, {"highest_education": "M.Tech Computer Science"}, {"highest_education": "B.Com"}),
            ({"occupation": "DOCTOR"}, {"occupation": "Junior doctor"}, {"occupation": "Teacher"}),
        ]
        for params, matching_fields, other_fields in cases:
            with self.subTest(params=params):
                Profile.objects.exclude(pk=self.me.pk).delete()
                yes, no = self.bride(**matching_fields), self.bride(**other_fields)
                found = self.codes(**params)
                self.assertIn(yes.profile_code, found)
                self.assertNotIn(no.profile_code, found)

    def test_filters_combine_with_and_and_repeatable_values_with_or(self):
        both = self.bride(religion="christian", community="", mother_tongue="tamil")
        religion_only = self.bride(religion="christian", community="", mother_tongue="malayalam")
        tongue_only = self.bride(religion="hindu", mother_tongue="tamil")
        self.assertEqual(self.codes(religion="christian", mother_tongue="tamil"), [both.profile_code])
        either = self.client.get(SEARCH, {"mother_tongue": ["tamil", "malayalam"]}).json()["results"]
        self.assertEqual(
            sorted(item["profile_code"] for item in either),
            sorted([both.profile_code, religion_only.profile_code, tongue_only.profile_code]),
        )
        self.assertEqual(sorted(self.codes(mother_tongue="tamil,malayalam")), sorted(i["profile_code"] for i in either))

    def test_profiles_without_the_detail_do_not_match_a_filter_on_it(self):
        unstated = self.bride(height_cm=None, religion="", marital_status="")
        self.assertIn(unstated.profile_code, self.codes())
        for params in ({"height_min": 150}, {"religion": "hindu"}, {"marital_status": "never_married"}):
            with self.subTest(params=params):
                self.assertNotIn(unstated.profile_code, self.codes(**params))


class AgeTests(SearchTestCase):
    def test_age_range_boundaries_respect_whether_the_birthday_has_passed(self):
        today = date(2026, 6, 15)
        turned_25_today = self.bride(date_of_birth=date(2001, 6, 15))
        turns_25_tomorrow = self.bride(date_of_birth=date(2001, 6, 16))
        turns_31_tomorrow = self.bride(date_of_birth=date(1995, 6, 16))  # still 30
        turned_31_today = self.bride(date_of_birth=date(1995, 6, 15))
        with mock.patch("apps.profiles.matching.date") as fake:
            fake.today.return_value = today
            found = self.codes(age_min=25, age_max=30)
        self.assertIn(turned_25_today.profile_code, found)
        self.assertNotIn(turns_25_tomorrow.profile_code, found)
        self.assertIn(turns_31_tomorrow.profile_code, found)
        self.assertNotIn(turned_31_today.profile_code, found)

    def test_age_is_the_same_year_as_the_card(self):
        bride = self.bride(age=26)
        self.assertEqual(self.get(age_min=26, age_max=26)["results"][0]["age"], 26)
        self.assertEqual(self.codes(age_min=27), [])
        self.assertEqual(self.codes(age_max=26), [bride.profile_code])


class ValidationTests(SearchTestCase):
    def test_invalid_values_are_rejected_with_field_errors(self):
        cases = {
            "age_min": {"age_min": "seventeen"},
            "age_max": {"age_min": 30, "age_max": 25},
            "height_max": {"height_min": 180, "height_max": 150},
            "religion": {"religion": "pastafarian"},
            "caste": {"religion": "hindu", "caste": "marthoma"},
            "location": {"location": "mars"},
            "marital_status": {"marital_status": "complicated"},
            "profile_id": {"profile_id": "12345"},
        }
        for field, params in cases.items():
            with self.subTest(field=field):
                self.assertIn(field, self.get(expect=400, **params))

    def test_out_of_range_ages_are_rejected(self):
        self.assertIn("age_min", self.get(expect=400, age_min=17))
        self.assertIn("age_max", self.get(expect=400, age_max=200))

    def test_gender_must_be_the_opposite_gender(self):
        bride = self.bride()
        self.assertEqual(self.codes(gender="female"), [bride.profile_code])
        body = self.get(expect=400, gender="male")
        self.assertEqual(body["gender"], ["Search shows brides for your profile."])

    def test_unknown_parameters_are_ignored(self):
        bride = self.bride()
        self.assertEqual(self.codes(color="blue", page_size="9999"), [bride.profile_code])


class VisibilityTests(SearchTestCase):
    def test_only_discoverable_opposite_gender_profiles_other_than_mine(self):
        visible = self.bride()
        hidden = [
            self.bride(status=ProfileStatus.DRAFT),
            self.bride(status=ProfileStatus.PENDING_REVIEW),
            self.bride(status=ProfileStatus.REJECTED),
            self.bride(status=ProfileStatus.SUSPENDED),
            self.bride(visibility=Visibility.HIDDEN),
            make_profile(gender="male"),
        ]
        inactive = self.bride()
        inactive.user.is_active = False
        inactive.user.save()
        found = self.codes()
        self.assertEqual(found, [visible.profile_code])
        # Asking for any of them by ID doesn't help either.
        for profile in [*hidden, inactive, self.me]:
            self.assertEqual(self.codes(profile_id=profile.profile_code), [])

    def test_members_only(self):
        self.assertEqual(client_for().get(SEARCH).status_code, 401)
        no_profile = client_for(make_user())
        response = no_profile.get(SEARCH)
        self.assertEqual((response.status_code, response.json()["code"]), (403, "no_profile"))

    def test_private_fields_are_never_returned(self):
        self.bride(about="Private bits", annual_income="10_20", income_visible=False)
        body = self.get()
        keys = set(walk_keys(body))
        for private in ("email", "phone_number", "date_of_birth", "review_note", "about", "annual_income",
                        "contact_sharing", "reviewed_by", "user", "id", "public_id"):
            self.assertNotIn(private, keys)
        self.assertEqual(body["searching_for"], "female")


class OrderingAndPaginationTests(SearchTestCase):
    def test_order_is_deterministic_and_pages_do_not_overlap(self):
        brides = [self.bride() for _ in range(25)]
        now = brides[0].created_at
        for i, profile in enumerate(brides):
            Profile.objects.filter(pk=profile.pk).update(reviewed_at=now - timedelta(minutes=i % 3))
        first, second = self.get(), self.get(page=2)
        self.assertEqual(first["count"], 25)
        codes = [i["profile_code"] for i in first["results"] + second["results"]]
        self.assertEqual(len(codes), 25)
        self.assertEqual(len(set(codes)), 25)  # no duplicates, nothing missing
        self.assertEqual(codes, [i["profile_code"] for i in self.get()["results"] + self.get(page=2)["results"]])

    def test_query_count_does_not_grow_with_results(self):
        self.bride()

        def count():
            with CaptureQueriesContext(connection) as queries:
                self.get()
            return len(queries)

        few = count()
        for _ in range(6):
            self.bride()
        self.assertEqual(count(), few)
