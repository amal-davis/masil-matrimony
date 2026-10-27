"""
Generating and keeping match recommendations (apps.matchmaking.models).

Scoring and eligibility are apps.profiles.matching's, unchanged and used by
the member's Matches page too, so staff and members never see two different
rules:
- eligibility: discoverable (approved, visible, active account), not the
  member, opposite gender, and every must-have the member filled in (a
  must-have with no data on the candidate isn't met);
- score: the share (0-100) of the member's filled-in criteria weights the
  candidate meets (matching.CRITERIA documents the weights); unstated details
  earn nothing and are listed as "not stated"; unspecified preferences don't
  count at all. A score is never shown without its reasons.

generate_for(member) evaluates the member's top MATCH_RECOMMENDATION_LIMIT
eligible candidates (the engine's ranking) and stores one recommendation per
candidate, idempotently:
- unchanged data (same fingerprint and algorithm) only refreshes
  last_evaluated_at: review decisions stay;
- changed data updates the result; an approved recommendation goes back to
  review when review is required (the decision history is kept);
  dismissed stays dismissed;
- a previous recommendation that no longer qualifies becomes "No longer a
  match" (never deleted).
It also evaluates the reverse direction for each candidate (does the member
suit the candidate's own preferences, must-haves included) so mutual
compatibility is right after a single member's run, and updates the pairs.

Review (MATCH_REVIEW_REQUIRED): off (default), recommendations are published
automatically and staff can still dismiss or flag one; on, members see only
approved ones. Approval is never consent to contact anyone.

Staleness: saving a profile or partner preferences marks the affected
recommendations stale (signals); preference changes also regenerate that
member's recommendations after the save (MATCH_REGENERATE_ON_CHANGE). The
generate_matches command re-evaluates stale ones and can run everything.
"""
import hashlib
import json
import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from apps.profiles import matching
from apps.profiles.choices import ProfileStatus
from apps.profiles.models import Profile

from .models import (
    MatchPair,
    MatchRecommendation,
    MatchRun,
    RecommendationStatus,
    ReviewEvent,
    ReviewStatus,
)

logger = logging.getLogger(__name__)

ALGORITHM_VERSION = "prefs-v1"
PROFILE_FIELDS = (
    "gender", "date_of_birth", "height_cm", "marital_status", "religion", "community", "mother_tongue", "diet",
    *matching.LOCATION_FIELDS, *matching.EDUCATION_FIELDS, "occupation",
)
PREFERENCE_FIELDS = tuple(
    f.name for f in matching.PartnerPreference._meta.concrete_fields
    if f.name not in ("id", "profile", "created_at", "updated_at", "notes")
)


def review_required() -> bool:
    return bool(settings.MATCH_REVIEW_REQUIRED)


def limit() -> int:
    return max(1, int(settings.MATCH_RECOMMENDATION_LIMIT))


def fingerprint(pref, candidate: Profile) -> str:
    """The data an evaluation depends on: the member's preferences and the candidate's details."""
    data = [ALGORITHM_VERSION, [getattr(pref, name) for name in PREFERENCE_FIELDS],
            [getattr(candidate, name) for name in PROFILE_FIELDS]]
    return hashlib.sha256(json.dumps(data, default=str, sort_keys=True).encode()).hexdigest()


def member_visible_q() -> Q:
    """Recommendations a member may be shown (on top of the engine's live eligibility)."""
    base = Q(hidden_by_member_at__isnull=True)
    if review_required():
        return base & Q(status=RecommendationStatus.ACTIVE, review_status=ReviewStatus.APPROVED)
    return base & ~Q(review_status__in=[ReviewStatus.DISMISSED, ReviewStatus.FLAGGED])


def is_visible(rec: MatchRecommendation) -> bool:
    if rec.hidden_by_member_at is not None:
        return False
    if review_required():
        return rec.status == RecommendationStatus.ACTIVE and rec.review_status == ReviewStatus.APPROVED
    return rec.status == RecommendationStatus.ACTIVE and rec.review_status not in (ReviewStatus.DISMISSED, ReviewStatus.FLAGGED)


@dataclass
class Result:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    withdrawn: int = 0

    def add(self, other: "Result"):
        for name in ("created", "updated", "unchanged", "withdrawn"):
            setattr(self, name, getattr(self, name) + getattr(other, name))


def _evaluate(member, pref, candidate, rec, now, result, to_create, to_update, requeued):
    explanation = matching.explain(member, candidate)
    digest = fingerprint(pref, candidate)
    values = {
        "score": explanation.score, "reasons": explanation.reasons, "mismatched": explanation.mismatched,
        "not_stated": explanation.not_stated, "reverse_must_haves_met": explanation.mutual,
        "algorithm_version": ALGORITHM_VERSION, "fingerprint": digest, "status": RecommendationStatus.ACTIVE,
        "last_evaluated_at": now,
    }
    if rec is None:
        to_create.append(MatchRecommendation(
            member=member, candidate=candidate, first_generated_at=now,
            review_status=ReviewStatus.PENDING if review_required() else ReviewStatus.NOT_REQUIRED, **values,
        ))
        result.created += 1
        return
    changed = (
        rec.fingerprint != digest or rec.algorithm_version != ALGORITHM_VERSION
        or rec.status != RecommendationStatus.ACTIVE or rec.reverse_must_haves_met != explanation.mutual
    )
    for name, value in values.items():
        setattr(rec, name, value)
    if changed:
        result.updated += 1
        if review_required() and rec.review_status in (ReviewStatus.APPROVED, ReviewStatus.NOT_REQUIRED):
            rec.review_status = ReviewStatus.PENDING
            requeued.append(rec)
    else:
        result.unchanged += 1
    to_update.append(rec)


UPDATE_FIELDS = [
    "score", "reasons", "mismatched", "not_stated", "reverse_must_haves_met", "algorithm_version", "fingerprint",
    "status", "last_evaluated_at", "review_status", "updated_at",
]


def generate_for(member: Profile, now=None) -> Result:
    """Evaluate one member's recommendations (and the reverse direction for each candidate). Idempotent."""
    now = now or timezone.now()
    result = Result()
    with transaction.atomic():
        member = Profile.objects.select_related("partner_preference", "user").get(pk=member.pk)
        pref = matching.preference_of(member)
        existing = {rec.candidate_id: rec for rec in MatchRecommendation.objects.select_for_update().filter(member=member)}
        candidates = []
        if member.status == ProfileStatus.ACTIVE and member.user.is_active and matching.has_preferences(pref):
            candidates = list(matching.ranked_candidates(member).select_related("partner_preference", "user")[: limit()])
        to_create, to_update, requeued = [], [], []
        for candidate in candidates:
            _evaluate(member, pref, candidate, existing.pop(candidate.pk, None), now, result, to_create, to_update, requeued)
        # Whatever is left no longer qualifies (or fell outside the limit): kept, marked, never deleted.
        for rec in existing.values():
            if rec.status != RecommendationStatus.INELIGIBLE:
                rec.status, rec.last_evaluated_at = RecommendationStatus.INELIGIBLE, now
                to_update.append(rec)
                result.withdrawn += 1

        # The other direction: does this member suit each candidate's own preferences?
        member_discoverable = Profile.objects.discoverable().filter(pk=member.pk).exists()
        reverse = {
            rec.member_id: rec
            for rec in MatchRecommendation.objects.select_for_update().filter(candidate=member, member__in=candidates)
        }
        for candidate in candidates:
            cpref = matching.preference_of(candidate)
            rec = reverse.get(candidate.pk)
            if member_discoverable and matching.has_preferences(cpref) and matching.meets_must_haves(cpref, member):
                _evaluate(candidate, cpref, member, rec, now, result, to_create, to_update, requeued)
            elif rec is not None and rec.status != RecommendationStatus.INELIGIBLE:
                rec.status, rec.last_evaluated_at = RecommendationStatus.INELIGIBLE, now
                to_update.append(rec)
                result.withdrawn += 1

        MatchRecommendation.objects.bulk_create(to_create, batch_size=500)
        for rec in to_update:
            rec.updated_at = now
        MatchRecommendation.objects.bulk_update(to_update, UPDATE_FIELDS, batch_size=500)
        ReviewEvent.objects.bulk_create([
            ReviewEvent(recommendation=rec, review_status=ReviewStatus.PENDING,
                        note="Profiles or preferences changed since the last review.")
            for rec in requeued
        ])
        refresh_pairs(member, [c.pk for c in candidates] + [rec.candidate_id for rec in to_update if rec.member_id == member.pk])
    return result


def refresh_pairs(member: Profile, other_ids) -> None:
    """Create or update the pair records between `member` and `other_ids` from their two directions."""
    ids = set(other_ids) - {member.pk}
    if not ids:
        return
    recs = MatchRecommendation.objects.filter(
        Q(member=member, candidate_id__in=ids) | Q(candidate=member, member_id__in=ids)
    )
    directions = {(rec.member_id, rec.candidate_id): rec for rec in recs}
    keys = {(min(member.pk, other), max(member.pk, other)) for other in ids}
    pairs = {
        (pair.profile_low_id, pair.profile_high_id): pair
        for pair in MatchPair.objects.select_for_update().filter(
            Q(profile_low=member, profile_high_id__in=ids) | Q(profile_high=member, profile_low_id__in=ids)
        )
    }
    now = timezone.now()
    to_create, to_update = [], []
    for low, high in keys:
        forward, backward = directions.get((low, high)), directions.get((high, low))
        if forward is None and backward is None:
            continue
        mutual = all(rec is not None and rec.status == RecommendationStatus.ACTIVE for rec in (forward, backward))
        pair = pairs.get((low, high))
        if pair is None:
            to_create.append(MatchPair(profile_low_id=low, profile_high_id=high, low_to_high=forward,
                                       high_to_low=backward, mutual=mutual, mutual_since=now if mutual else None))
            continue
        if (pair.low_to_high_id, pair.high_to_low_id, pair.mutual) != (getattr(forward, "pk", None), getattr(backward, "pk", None), mutual):
            pair.low_to_high, pair.high_to_low = forward, backward
            pair.mutual_since = (pair.mutual_since or now) if mutual else None
            pair.mutual, pair.updated_at = mutual, now
            to_update.append(pair)
    MatchPair.objects.bulk_create(to_create)
    MatchPair.objects.bulk_update(to_update, ["low_to_high", "high_to_low", "mutual", "mutual_since", "updated_at"])


def eligible_members():
    """Members recommendations are generated for: approved profiles of active accounts."""
    return Profile.objects.filter(status=ProfileStatus.ACTIVE, user__is_active=True)


def run(members, trigger: str, staff=None, batch_size: int = 200) -> MatchRun:
    """Generate for many members, in batches; one member's failure doesn't stop the rest."""
    record = MatchRun.objects.create(trigger=trigger, triggered_by=staff)
    total = Result()
    ids = list(members.order_by("pk").values_list("pk", flat=True))
    for start in range(0, len(ids), batch_size):
        for profile in Profile.objects.filter(pk__in=ids[start:start + batch_size]).order_by("pk"):
            try:
                total.add(generate_for(profile))
                record.members_evaluated += 1
            except Exception:  # noqa: BLE001 - logged and counted; the run carries on
                record.failures += 1
                logger.exception("Match generation failed for profile %s", profile.pk)
    for name in ("created", "updated", "unchanged", "withdrawn"):
        setattr(record, name, getattr(total, name))
    record.finished_at = timezone.now()
    record.save()
    return record


# --- Review ------------------------------------------------------------------------


def review(recs, staff, decision: str, note: str = "") -> int:
    """Record a staff decision on each recommendation. Only current ones can be approved."""
    if decision not in (ReviewStatus.APPROVED, ReviewStatus.DISMISSED, ReviewStatus.FLAGGED):
        raise ValueError("Unknown decision.")
    if decision == ReviewStatus.DISMISSED and not note.strip():
        raise ValueError("Give a reason for dismissing.")
    now, changed = timezone.now(), 0
    with transaction.atomic():
        queryset = MatchRecommendation.objects.select_for_update().filter(pk__in=[rec.pk for rec in recs])
        if decision == ReviewStatus.APPROVED:
            queryset = queryset.filter(status=RecommendationStatus.ACTIVE)
        for rec in queryset:
            rec.review_status, rec.reviewed_by, rec.reviewed_at, rec.review_note = decision, staff, now, note.strip()[:300]
            rec.save(update_fields=["review_status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])
            ReviewEvent.objects.create(recommendation=rec, review_status=decision, note=rec.review_note, staff=staff)
            changed += 1
    return changed


def hide_for_member(member: Profile, candidate: Profile) -> MatchRecommendation:
    """The member's "Hide this suggestion". Records it even if no recommendation was stored yet."""
    now = timezone.now()
    rec, created = MatchRecommendation.objects.get_or_create(
        member=member, candidate=candidate,
        defaults={
            "algorithm_version": ALGORITHM_VERSION, "fingerprint": "", "status": RecommendationStatus.STALE,
            "review_status": ReviewStatus.PENDING if review_required() else ReviewStatus.NOT_REQUIRED,
            "first_generated_at": now, "last_evaluated_at": now, "hidden_by_member_at": now,
        },
    )
    if not created and rec.hidden_by_member_at is None:
        rec.hidden_by_member_at = now
        rec.save(update_fields=["hidden_by_member_at", "updated_at"])
    return rec


def mark_stale(**filters) -> int:
    return MatchRecommendation.objects.filter(status=RecommendationStatus.ACTIVE, **filters).update(
        status=RecommendationStatus.STALE, updated_at=timezone.now()
    )


# --- Analytics -----------------------------------------------------------------------


def incomplete_preference_members():
    """Approved members whose saved preferences contain no criterion (or who have none)."""
    with_any = [
        profile_id for profile_id, *values in
        matching.PartnerPreference.objects.filter(profile__in=eligible_members())
        .values_list("profile_id", *PREFERENCE_FIELDS).iterator(chunk_size=1000)
        if matching.has_preferences(matching.PartnerPreference(**dict(zip(PREFERENCE_FIELDS, values))))
    ]
    return eligible_members().exclude(pk__in=with_any)


def analytics(start=None, end=None) -> dict:
    """Real counts (the analytics page explains each). One query per group of figures."""
    from apps.interactions.models import Interest, InterestStatus

    recs = MatchRecommendation.objects.all()
    counts = recs.aggregate(
        total=Count("pk"),
        current=Count("pk", filter=Q(status=RecommendationStatus.ACTIVE)),
        stale=Count("pk", filter=Q(status=RecommendationStatus.STALE)),
        withdrawn=Count("pk", filter=Q(status=RecommendationStatus.INELIGIBLE)),
        pending=Count("pk", filter=Q(review_status=ReviewStatus.PENDING, status=RecommendationStatus.ACTIVE)),
        flagged=Count("pk", filter=Q(review_status=ReviewStatus.FLAGGED)),
        approved=Count("pk", filter=Q(review_status=ReviewStatus.APPROVED)),
        dismissed=Count("pk", filter=Q(review_status=ReviewStatus.DISMISSED)),
        hidden=Count("pk", filter=Q(hidden_by_member_at__isnull=False)),
        members=Count("member", distinct=True, filter=Q(status=RecommendationStatus.ACTIVE)),
    )
    if start or end:
        period = Q()
        if start:
            period &= Q(first_generated_at__gte=start)
        if end:
            period &= Q(first_generated_at__lt=end)
        counts["in_period"] = recs.filter(period).count()
    accepted = Interest.objects.filter(status=InterestStatus.ACCEPTED).filter(
        Q(sender=OuterRef("profile_low"), receiver=OuterRef("profile_high"))
        | Q(sender=OuterRef("profile_high"), receiver=OuterRef("profile_low"))
    )
    pairs = MatchPair.objects.aggregate(
        pairs=Count("pk"),
        mutual=Count("pk", filter=Q(mutual=True)),
    )
    pairs["mutual_accepted"] = MatchPair.objects.filter(mutual=True).filter(Exists(accepted)).count()
    pairs["accepted_interests"] = Interest.objects.filter(status=InterestStatus.ACCEPTED).count()
    last_run = MatchRun.objects.filter(finished_at__isnull=False).first()
    return {
        **counts, **pairs,
        "eligible_members": eligible_members().count(),
        "incomplete": incomplete_preference_members().count(),
        "last_run": last_run,
    }


def gate_for_member(member: Profile, candidates):
    """
    The member's live matches minus what they hid or staff dismissed/flagged; with
    review required, only approved current recommendations.
    """
    mine = MatchRecommendation.objects.filter(member=member)
    if review_required():
        return candidates.filter(pk__in=mine.filter(member_visible_q()).values("candidate_id"))
    return candidates.exclude(pk__in=mine.exclude(member_visible_q()).values("candidate_id"))
