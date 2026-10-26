"""
Member-driven profile search: GET /api/v1/profiles/search/.

Search applies only the filters the member chose. It never adds their saved
partner preferences (that's matchmaking: apps.profiles.matching).

Who can be found: the same profiles as in matches and on profile pages.
  - discoverable: approved by staff, visibility "members", owner's account
    active (Profile.objects.discoverable());
  - not the member themself;
  - of the opposite gender (the site's matrimonial rule, as in matching).
    `gender` may be sent; anything other than the opposite gender is refused.

How filters combine: every filter given must match (AND). A filter that accepts
several values (marital_status, mother_tongue) matches any of them (OR). An
empty or missing filter restricts nothing. A profile that hasn't stated a
detail doesn't match a filter on that detail.

  age_min, age_max          whole years, 18-80, from date of birth (birthdays counted exactly)
  height_min, height_max    centimetres
  religion                  hindu | christian | muslim | other
  caste                     community code (apps.profiles.choices.COMMUNITIES); must belong to `religion` if both given
  location                  a Kerala district (thrissur, ...), rest-of-india or abroad
  marital_status            never_married | divorced | widowed | awaiting_divorce (repeatable)
  mother_tongue             malayalam | tamil | ... (repeatable)
  education, occupation     text, case-insensitive, matched anywhere in the field
  profile_id                Matrimony ID, e.g. MM482913 (case-insensitive)

Order: most recently approved first, then newest profile, so pages are stable.
"""
from django.db.models import F, Q, QuerySet
from rest_framework import serializers

from .choices import ALL_COMMUNITIES, COMMUNITIES, MAX_AGE, Gender, MaritalStatus, MotherTongue, Religion
from .matching import birth_date_bounds
from .models import HEIGHT_VALIDATORS, Profile

KERALA_DISTRICTS = {
    name.lower(): name
    for name in (
        "Thiruvananthapuram", "Kollam", "Pathanamthitta", "Alappuzha", "Kottayam", "Idukki", "Ernakulam",
        "Thrissur", "Palakkad", "Malappuram", "Kozhikode", "Wayanad", "Kannur", "Kasaragod",
    )
}
REST_OF_INDIA = "rest-of-india"
ABROAD = "abroad"
LOCATIONS = {*KERALA_DISTRICTS, REST_OF_INDIA, ABROAD}

MIN_SEARCH_AGE = 18
HEIGHT_MIN_CM = HEIGHT_VALIDATORS[0].limit_value
HEIGHT_MAX_CM = HEIGHT_VALIDATORS[1].limit_value


def _clean_text(value: str) -> str:
    """Trimmed, inner whitespace collapsed."""
    return " ".join(value.split())


class SearchFilters(serializers.Serializer):
    gender = serializers.ChoiceField(choices=Gender.choices, required=False)
    age_min = serializers.IntegerField(min_value=MIN_SEARCH_AGE, max_value=MAX_AGE, required=False)
    age_max = serializers.IntegerField(min_value=MIN_SEARCH_AGE, max_value=MAX_AGE, required=False)
    height_min = serializers.IntegerField(min_value=HEIGHT_MIN_CM, max_value=HEIGHT_MAX_CM, required=False)
    height_max = serializers.IntegerField(min_value=HEIGHT_MIN_CM, max_value=HEIGHT_MAX_CM, required=False)
    religion = serializers.ChoiceField(choices=Religion.choices, required=False)
    caste = serializers.ChoiceField(choices=sorted(ALL_COMMUNITIES.items()), required=False)
    location = serializers.ChoiceField(choices=sorted(LOCATIONS), required=False)
    marital_status = serializers.ListField(
        child=serializers.ChoiceField(choices=MaritalStatus.choices), required=False, max_length=len(MaritalStatus)
    )
    mother_tongue = serializers.ListField(
        child=serializers.ChoiceField(choices=MotherTongue.choices), required=False, max_length=len(MotherTongue)
    )
    education = serializers.CharField(max_length=60, required=False)
    occupation = serializers.CharField(max_length=60, required=False)
    profile_id = serializers.RegexField(
        r"^[Mm]{2}\d{6}$", required=False, error_messages={"invalid": "Enter a Matrimony ID such as MM482913."}
    )

    @classmethod
    def from_query(cls, query_params, **kwargs) -> "SearchFilters":
        """Empty parameters mean "any"; repeatable ones accept ?x=a&x=b or ?x=a,b."""
        data = {}
        for name, field in cls().fields.items():
            if isinstance(field, serializers.ListField):
                values = [part.strip() for raw in query_params.getlist(name) for part in raw.split(",")]
                values = list(dict.fromkeys(value for value in values if value))
                if values:
                    data[name] = values
            else:
                value = (query_params.get(name) or "").strip()
                if value:
                    data[name] = value
        return cls(data=data, **kwargs)

    def validate_education(self, value):
        return _clean_text(value)

    def validate_occupation(self, value):
        return _clean_text(value)

    def validate_profile_id(self, value):
        return value.upper()

    def validate(self, attrs):
        errors = {}
        if attrs.get("age_min") and attrs.get("age_max") and attrs["age_min"] > attrs["age_max"]:
            errors["age_max"] = "The maximum age can't be lower than the minimum."
        if attrs.get("height_min") and attrs.get("height_max") and attrs["height_min"] > attrs["height_max"]:
            errors["height_max"] = "The maximum height can't be lower than the minimum."
        religion, caste = attrs.get("religion"), attrs.get("caste")
        if religion and caste and caste not in COMMUNITIES[religion]:
            errors["caste"] = "Choose a community for the selected religion."
        viewer = self.context.get("viewer")
        if viewer is not None and attrs.get("gender") and attrs["gender"] != searchable_gender(viewer):
            looking_for = "brides" if searchable_gender(viewer) == Gender.FEMALE else "grooms"
            errors["gender"] = f"Search shows {looking_for} for your profile."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


def searchable_gender(viewer: Profile) -> str:
    return Gender.FEMALE if viewer.gender == Gender.MALE else Gender.MALE


def _location_q(location: str) -> Q:
    if location in KERALA_DISTRICTS:
        name = KERALA_DISTRICTS[location]
        return Q(district__iexact=name) | Q(city__iexact=name)
    in_india = Q(country__iexact="india") | Q(country="")
    if location == REST_OF_INDIA:
        return in_india & ~Q(state__iexact="kerala")
    return ~in_india  # abroad


def search_profiles(viewer: Profile, filters: dict) -> QuerySet:
    """Eligible profiles matching every given filter, in a stable order. `filters` is SearchFilters.validated_data."""
    queryset = Profile.objects.discoverable().exclude(pk=viewer.pk).filter(gender=searchable_gender(viewer))

    earliest, latest = birth_date_bounds(filters.get("age_min"), filters.get("age_max"))
    if earliest:
        queryset = queryset.filter(date_of_birth__gt=earliest)
    if latest:
        queryset = queryset.filter(date_of_birth__lte=latest)
    if filters.get("height_min"):
        queryset = queryset.filter(height_cm__gte=filters["height_min"])
    if filters.get("height_max"):
        queryset = queryset.filter(height_cm__lte=filters["height_max"])
    if filters.get("religion"):
        queryset = queryset.filter(religion=filters["religion"])
    if filters.get("caste"):
        queryset = queryset.filter(community=filters["caste"])
    if filters.get("location"):
        queryset = queryset.filter(_location_q(filters["location"]))
    if filters.get("marital_status"):
        queryset = queryset.filter(marital_status__in=filters["marital_status"])
    if filters.get("mother_tongue"):
        queryset = queryset.filter(mother_tongue__in=filters["mother_tongue"])
    if filters.get("education"):
        text = filters["education"]
        queryset = queryset.filter(Q(highest_education__icontains=text) | Q(education_detail__icontains=text))
    if filters.get("occupation"):
        queryset = queryset.filter(occupation__icontains=filters["occupation"])
    if filters.get("profile_id"):
        queryset = queryset.filter(profile_code=filters["profile_id"])

    # One row per profile (no joins that fan out), so no duplicates without DISTINCT.
    return queryset.order_by(F("reviewed_at").desc(nulls_last=True), "-pk")
