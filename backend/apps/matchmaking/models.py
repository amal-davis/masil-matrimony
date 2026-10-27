"""
Stored results of the partner-preference matching engine (apps.profiles.matching),
for staff review, analytics and member-side hiding (apps.matchmaking.engine).

- MatchRecommendation: one direction, "candidate suits member's preferences",
  with the engine's score and explanation when last evaluated. One per
  (member, candidate).
- MatchPair: the unordered pair, once per pair (low profile id first), linking
  the two directions. Mutual compatibility = both directions are current
  recommendations: each member meets the other's must-haves.
- MatchRun: one generation run (command, admin action or single member), for
  operations and analytics.

Mutual *interest* (both sent interests) and an accepted interest are read live
from apps.interactions; they are never stored here, and neither is consent.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel


class RecommendationStatus(models.TextChoices):
    # Passed the member's must-haves at the last evaluation, with current data.
    ACTIVE = "active", "Current"
    # The member's preferences or either profile changed since: re-evaluated on the next run.
    STALE = "stale", "Needs re-evaluation"
    # No longer passes (must-haves, visibility, approval) or the member removed every preference.
    INELIGIBLE = "ineligible", "No longer a match"


class ReviewStatus(models.TextChoices):
    # Published automatically (MATCH_REVIEW_REQUIRED off).
    NOT_REQUIRED = "not_required", "Published automatically"
    PENDING = "pending", "Awaiting review"
    APPROVED = "approved", "Approved"
    FLAGGED = "flagged", "Flagged for further review"
    DISMISSED = "dismissed", "Dismissed"


class MatchRecommendation(TimeStampedModel):
    member = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="recommendations")
    candidate = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="recommended_to")
    score = models.PositiveSmallIntegerField(null=True, blank=True, help_text="0-100 share of the member's preference points.")
    # From apps.profiles.matching.explain, about the member's own preferences.
    reasons = models.JSONField(default=list, blank=True)
    mismatched = models.JSONField(default=list, blank=True)
    not_stated = models.JSONField(default=list, blank=True)
    # The member also meets every must-have of the candidate (the engine's "mutual" check).
    reverse_must_haves_met = models.BooleanField(default=False)
    algorithm_version = models.CharField(max_length=20)
    # Hash of the data the evaluation used: unchanged data keeps the review decision.
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=RecommendationStatus.choices, default=RecommendationStatus.ACTIVE,
                              db_index=True)
    review_status = models.CharField(max_length=12, choices=ReviewStatus.choices, db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=300, blank=True, help_text="Dismissal reason or what to look at.")
    # The member chose "Hide this suggestion".
    hidden_by_member_at = models.DateTimeField(null=True, blank=True)
    first_generated_at = models.DateTimeField()
    last_evaluated_at = models.DateTimeField()

    class Meta:
        ordering = ["-last_evaluated_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["member", "candidate"], name="unique_recommendation_direction"),
            models.CheckConstraint(condition=~Q(member=F("candidate")), name="recommendation_not_self"),
        ]
        indexes = [models.Index(fields=["member", "status", "score"]), models.Index(fields=["first_generated_at"])]
        permissions = [
            ("review_matchrecommendation", "Can approve, dismiss or flag match recommendations"),
            ("generate_matchrecommendation", "Can generate and refresh match recommendations"),
        ]
        verbose_name = "auto-matched profile"

    def __str__(self):
        return f"{self.candidate_id} for {self.member_id}"


class PendingRecommendation(MatchRecommendation):
    """The review queue: recommendations awaiting review or flagged."""

    class Meta:
        proxy = True
        verbose_name = "recommendation to review"
        verbose_name_plural = "match review queue"


class MatchPair(TimeStampedModel):
    profile_low = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="+")
    profile_high = models.ForeignKey("profiles.Profile", on_delete=models.CASCADE, related_name="+")
    # low's preferences -> high, and high's preferences -> low.
    low_to_high = models.OneToOneField(MatchRecommendation, null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name="+")
    high_to_low = models.OneToOneField(MatchRecommendation, null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name="+")
    mutual = models.BooleanField(default=False, db_index=True)
    mutual_since = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["profile_low", "profile_high"], name="unique_match_pair"),
            models.CheckConstraint(condition=Q(profile_low__lt=F("profile_high")), name="match_pair_canonical_order"),
        ]
        verbose_name = "match pair"

    def __str__(self):
        return f"{self.profile_low_id} & {self.profile_high_id}"


class MutualMatch(MatchPair):
    class Meta:
        proxy = True
        verbose_name = "mutual match"
        verbose_name_plural = "mutual matches"


class MatchRun(models.Model):
    """One generation run."""

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    trigger = models.CharField(max_length=20, help_text="command, admin, member_change …")
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    members_evaluated = models.PositiveIntegerField(default=0)
    created = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    unchanged = models.PositiveIntegerField(default=0)
    withdrawn = models.PositiveIntegerField(default=0)
    failures = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Run {self.pk} ({self.trigger})"


class ReviewEvent(models.Model):
    """One review decision (or automatic re-queue after the data changed). Append-only."""

    recommendation = models.ForeignKey(MatchRecommendation, on_delete=models.CASCADE, related_name="review_events")
    review_status = models.CharField(max_length=12, choices=ReviewStatus.choices)
    note = models.CharField(max_length=300, blank=True)
    # Null when the system re-queued it because the profiles or preferences changed.
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return self.get_review_status_display()
