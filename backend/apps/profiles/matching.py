"""
Partner-preference matchmaking: which profiles a member is shown as matches,
in what order, and why. Results are computed on every request from the saved
preferences, so a change to them (or to anyone's profile) applies at once.

Two stages, kept apart so a high score can never outweigh a requirement.

1. Eligibility: database filters. A candidate must be
   - discoverable: approved by staff, visibility "members", owner's account
     active (Profile.objects.discoverable());
   - not the member themself, and of the opposite gender (the site's
     existing matrimonial rule);
   - a match for every criterion the member marked as a must-have
     (PartnerPreference.must_haves) and filled in. A must-have is never
     relaxed to fill the list.
   A must-have the candidate has no data for (e.g. no height) is not met.

2. Ranking: every criterion the member filled in is worth CRITERIA weight
   points. The score is the share of those points the candidate earns, as a
   whole percentage (0-100). Must-haves count too: every eligible candidate
   earns them. A detail the candidate hasn't stated earns nothing (missing data
   is never treated as a match) and is listed under "not stated". Ties go
   first to profiles with Priority Profile Visibility (Gold, Diamond;
   apps.profiles.priority), then the most recently approved profile, then the
   newest profile, so the order is stable across pages. With no preferences
   filled in there is no score, and the list is priority first, then newest
   approved.

Mutual: a candidate is a mutual match when the member also meets every
must-have the candidate has set (an unset or empty criterion restricts
nothing). Only that yes/no is returned: never the candidate's preferences.

Free-text preferences (locations, education, occupation) are split on commas,
semicolons, slashes or new lines into terms. A term matches when it appears as
a whole word or phrase, ignoring case, in the candidate's city, district, state,
country or native place / highest education or qualification / occupation.
Each rule is written twice, as a database filter (`q`) for eligibility and
ranking and in Python (`test`) for explanations and mutual checks; the test
suite checks that the two agree.
"""
import functools
import operator
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from django.db.models import Case, IntegerField, Q, QuerySet, Value, When

from .choices import Gender
from .models import PartnerPreference, Profile
from .priority import annotate_priority

# --- Free-text terms ---------------------------------------------------------

_TERM_SEPARATORS = re.compile(r"[,;/|\n]+")
# Letters (any script), digits, spaces and . & + ' - only: nothing else reaches a regular expression.
_TERM_JUNK = re.compile(r"[^\w .&+'-]")
MAX_TERMS = 10


def terms(text: str) -> list[str]:
    """The distinct search terms in a free-text preference, lower-cased."""
    found = []
    for part in _TERM_SEPARATORS.split(text or ""):
        term = " ".join(_TERM_JUNK.sub(" ", part).split()).lower()
        if 2 <= len(term) <= 40 and term not in found:
            found.append(term)
    return found[:MAX_TERMS]


def _word_pattern(term: str) -> str:
    # Not \b: it means different things in MySQL 8 (ICU), MariaDB (PCRE) and Python.
    return r"(^|[^a-z0-9])" + re.escape(term) + r"([^a-z0-9]|$)"


def _text_q(pref_text: str, fields: tuple[str, ...]) -> Q:
    conditions = [Q(**{f"{name}__iregex": _word_pattern(term)}) for term in terms(pref_text) for name in fields]
    return functools.reduce(operator.or_, conditions)


def _text_test(pref_text: str, values: list[str]) -> bool:
    return any(
        re.search(_word_pattern(term), value or "", re.IGNORECASE) for term in terms(pref_text) for value in values
    )


# --- Age -----------------------------------------------------------------------


def _years_ago(years: int, today: date) -> date:
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # 29 February
        return today.replace(year=today.year - years, day=28)


def birth_date_bounds(age_min, age_max, today: date | None = None):
    """(earliest, latest): born after `earliest` and on or before `latest` means age_min <= age <= age_max."""
    today = today or date.today()
    latest = _years_ago(age_min, today) if age_min else None
    earliest = _years_ago(age_max + 1, today) if age_max else None
    return earliest, latest


def _age_q(pref) -> Q:
    earliest, latest = birth_date_bounds(pref.age_min, pref.age_max)
    q = Q()
    if earliest:
        q &= Q(date_of_birth__gt=earliest)
    if latest:
        q &= Q(date_of_birth__lte=latest)
    return q


def _age_test(pref, profile) -> bool:
    earliest, latest = birth_date_bounds(pref.age_min, pref.age_max)
    born = profile.date_of_birth
    return born is not None and (not earliest or born > earliest) and (not latest or born <= latest)


def _range_text(low, high, unit="") -> str:
    if low and high:
        return f"{low}–{high}{unit}"
    return f"{low}{unit}+" if low else f"up to {high}{unit}"


# --- Height -------------------------------------------------------------------


def _height_q(pref) -> Q:
    q = Q(height_cm__isnull=False)
    if pref.height_min_cm:
        q &= Q(height_cm__gte=pref.height_min_cm)
    if pref.height_max_cm:
        q &= Q(height_cm__lte=pref.height_max_cm)
    return q


def _height_test(pref, profile) -> bool:
    height = profile.height_cm
    return (
        height is not None
        and (not pref.height_min_cm or height >= pref.height_min_cm)
        and (not pref.height_max_cm or height <= pref.height_max_cm)
    )


# --- Criteria -------------------------------------------------------------------


@dataclass(frozen=True)
class Criterion:
    key: str
    # How the member's settings name it.
    label: str
    weight: int
    configured: Callable[[PartnerPreference], bool]
    # The candidate matches: a database filter and the same rule in Python.
    q: Callable[[PartnerPreference], Q]
    test: Callable[[PartnerPreference, Profile], bool]
    # The candidate has stated this detail at all.
    stated: Callable[[Profile], bool]
    # Shown to the member when a candidate matches. Only ever about the member's own preference.
    reason: Callable[[PartnerPreference], str]


def _choice(key, label, weight, pref_field, profile_field, reason) -> Criterion:
    return Criterion(
        key=key,
        label=label,
        weight=weight,
        configured=lambda pref: bool(getattr(pref, pref_field)),
        q=lambda pref: Q(**{f"{profile_field}__in": list(getattr(pref, pref_field))}),
        test=lambda pref, profile: bool(getattr(profile, profile_field))
        and getattr(profile, profile_field) in getattr(pref, pref_field),
        stated=lambda profile: bool(getattr(profile, profile_field)),
        reason=lambda pref: reason,
    )


def _text(key, label, weight, pref_field, profile_fields, reason) -> Criterion:
    return Criterion(
        key=key,
        label=label,
        weight=weight,
        configured=lambda pref: bool(terms(getattr(pref, pref_field))),
        q=lambda pref: _text_q(getattr(pref, pref_field), profile_fields),
        test=lambda pref, profile: _text_test(getattr(pref, pref_field), [getattr(profile, f) for f in profile_fields]),
        stated=lambda profile: any(getattr(profile, f) for f in profile_fields),
        reason=lambda pref: reason,
    )


LOCATION_FIELDS = ("city", "district", "state", "country", "native_place")
EDUCATION_FIELDS = ("highest_education", "education_detail")

# Weights are points out of the total of the criteria a member has filled in (see the module docstring).
CRITERIA: tuple[Criterion, ...] = (
    Criterion(
        key="age",
        label="Age",
        weight=20,
        configured=lambda pref: bool(pref.age_min or pref.age_max),
        q=_age_q,
        test=_age_test,
        stated=lambda profile: profile.date_of_birth is not None,
        reason=lambda pref: f"Matches your age preference ({_range_text(pref.age_min, pref.age_max)})",
    ),
    _choice("marital_status", "Marital status", 15, "marital_statuses", "marital_status",
            "Matches your marital status preference"),
    _choice("religion", "Religion", 15, "religions", "religion", "Matches your religion preference"),
    _text("location", "Location", 12, "locations", LOCATION_FIELDS, "Lives in or comes from a place you prefer"),
    _choice("community", "Community", 10, "communities", "community", "Matches your community preference"),
    _choice("mother_tongue", "Mother tongue", 8, "mother_tongues", "mother_tongue",
            "Matches your mother tongue preference"),
    _text("education", "Education", 8, "education", EDUCATION_FIELDS, "Matches your education preference"),
    _text("occupation", "Occupation", 6, "occupation", ("occupation",), "Matches your occupation preference"),
    Criterion(
        key="height",
        label="Height",
        weight=6,
        configured=lambda pref: bool(pref.height_min_cm or pref.height_max_cm),
        q=_height_q,
        test=_height_test,
        stated=lambda profile: profile.height_cm is not None,
        reason=lambda pref: f"Matches your height preference ({_range_text(pref.height_min_cm, pref.height_max_cm, ' cm')})",
    ),
    _choice("diet", "Diet", 5, "diets", "diet", "Matches your diet preference"),
)

CRITERIA_BY_KEY = {criterion.key: criterion for criterion in CRITERIA}
CRITERION_KEYS = tuple(CRITERIA_BY_KEY)


# --- Preferences ----------------------------------------------------------------


def preference_of(profile: Profile) -> PartnerPreference | None:
    try:
        return profile.partner_preference
    except PartnerPreference.DoesNotExist:
        return None


def configured_criteria(pref: PartnerPreference | None) -> list[Criterion]:
    return [criterion for criterion in CRITERIA if pref is not None and criterion.configured(pref)]


def must_have_criteria(pref: PartnerPreference | None) -> list[Criterion]:
    """The filled-in criteria the member requires. Unknown keys are ignored."""
    required = set(pref.must_haves or []) if pref is not None else set()
    return [criterion for criterion in configured_criteria(pref) if criterion.key in required]


def has_preferences(pref: PartnerPreference | None) -> bool:
    return bool(configured_criteria(pref))


def meets_must_haves(pref: PartnerPreference | None, profile: Profile) -> bool:
    """Whether `profile` satisfies every must-have in `pref` (an empty preference restricts nothing)."""
    return all(criterion.test(pref, profile) for criterion in must_have_criteria(pref))


# --- Candidates ---------------------------------------------------------------------


def eligible_candidates(member: Profile) -> QuerySet:
    """Stage 1: everyone the member may be shown, before ranking. Unordered."""
    pref = preference_of(member)
    queryset = (
        Profile.objects.discoverable()
        .exclude(pk=member.pk)
        .filter(gender=Gender.FEMALE if member.gender == Gender.MALE else Gender.MALE)
    )
    for criterion in must_have_criteria(pref):
        queryset = queryset.filter(criterion.q(pref))
    return queryset


def mutual_candidate_ids(member: Profile, candidates: QuerySet) -> list[int]:
    """
    The candidates whose own must-haves the member meets. Reads only each
    candidate's preference row (one query); the member's profile is the subject.
    """
    pref_fields = [f.name for f in PartnerPreference._meta.concrete_fields if f.name not in ("id", "profile", "created_at", "updated_at")]
    rows = candidates.values("pk", *(f"partner_preference__{name}" for name in pref_fields))
    mutual = []
    for row in rows:
        if row["partner_preference__must_haves"] is None:  # no preference row: no requirements
            mutual.append(row["pk"])
            continue
        their_pref = PartnerPreference(**{name: row[f"partner_preference__{name}"] for name in pref_fields})
        if meets_must_haves(their_pref, member):
            mutual.append(row["pk"])
    return mutual


def ranked_candidates(member: Profile, *, mutual_only: bool = False) -> QuerySet:
    """
    Stage 2: eligible candidates, best match first (see the module docstring).
    Annotated with `match_points`, the points earned on the optional criteria.
    """
    pref = preference_of(member)
    queryset = eligible_candidates(member)
    if mutual_only:
        queryset = queryset.filter(pk__in=mutual_candidate_ids(member, queryset))

    required = {criterion.key for criterion in must_have_criteria(pref)}
    optional = [criterion for criterion in configured_criteria(pref) if criterion.key not in required]
    # Priority visibility (apps.profiles.priority) only orders equal matches.
    queryset = annotate_priority(queryset)
    if not optional:
        return queryset.order_by("-priority", "-reviewed_at", "-pk")
    points = functools.reduce(
        operator.add,
        [
            Case(When(criterion.q(pref), then=Value(criterion.weight)), default=Value(0), output_field=IntegerField())
            for criterion in optional
        ],
    )
    return queryset.annotate(match_points=points).order_by("-match_points", "-priority", "-reviewed_at", "-pk")


# --- Explanations -----------------------------------------------------------------


@dataclass
class MatchExplanation:
    # 0-100, or None when the member has no preferences filled in.
    score: int | None
    # Short statements about the member's own preferences that this candidate meets, most important first.
    reasons: list[str] = field(default_factory=list)
    # Labels of preferred details this candidate hasn't stated.
    not_stated: list[str] = field(default_factory=list)
    # The member also meets every must-have the candidate has set.
    mutual: bool = False
    # Labels of preferred details the candidate stated but that don't match. For staff
    # (apps.matchmaking); not part of the member's view (as_dict).
    mismatched: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"score": self.score, "reasons": self.reasons, "not_stated": self.not_stated, "mutual": self.mutual}


def explain(member: Profile, candidate: Profile) -> MatchExplanation:
    """Why `candidate` is on `member`'s list. Uses only already-loaded rows (no queries)."""
    pref = preference_of(member)
    criteria = configured_criteria(pref)
    earned = 0
    reasons, not_stated, mismatched = [], [], []
    for criterion in criteria:
        if criterion.test(pref, candidate):
            earned += criterion.weight
            reasons.append(criterion.reason(pref))
        elif not criterion.stated(candidate):
            not_stated.append(criterion.label)
        else:
            mismatched.append(criterion.label)
    total = sum(criterion.weight for criterion in criteria)
    return MatchExplanation(
        score=round(100 * earned / total) if total else None,
        reasons=reasons,
        not_stated=not_stated,
        mutual=meets_must_haves(preference_of(candidate), member),
        mismatched=mismatched,
    )
