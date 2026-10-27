"""
Matchmaking Management in the admin: auto-matched profiles, the review queue,
mutual matches, generation runs and analytics (apps.matchmaking.engine).

Nothing here edits a score or an explanation: they come only from the engine,
recalculated with "Refresh". Reviews are recorded with who and when, and kept
in each recommendation's history. Approving a recommendation only lets the
member see it; it is never either member's consent to be contacted.

Permissions: view_matchrecommendation to look; review_matchrecommendation to
approve, dismiss or flag; generate_matchrecommendation to generate or refresh.
"""
from datetime import datetime, time, timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.exceptions import PermissionDenied
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline

from apps.interactions.models import Interest, InterestStatus
from apps.profiles.models import Profile

from . import engine
from .models import (
    MatchPair,
    MatchRecommendation,
    MatchRun,
    MutualMatch,
    PendingRecommendation,
    RecommendationStatus,
    ReviewEvent,
    ReviewStatus,
)

REVIEW = "matchmaking.review_matchrecommendation"
GENERATE = "matchmaking.generate_matchrecommendation"


def profile_link(profile) -> str:
    return format_html('<a href="{}">{} ({})</a>', reverse("admin:profiles_profile_change", args=[profile.pk]),
                       profile.display_name, profile.profile_code)


def bullet_list(items) -> str:
    return format_html_join(mark_safe("<br>"), "• {}", ((item,) for item in items)) if items else "—"


def interest_q(a, b) -> Q:
    return Q(sender=a, receiver=b) | Q(sender=b, receiver=a)


def interest_state(a, b) -> str:
    """Mutual interest (both sent one) and an accepted interest are separate from compatibility."""
    interests = list(Interest.objects.filter(interest_q(a, b)).exclude(status=InterestStatus.WITHDRAWN))
    if any(item.status == InterestStatus.ACCEPTED for item in interests):
        return "Interest accepted"
    senders = {item.sender_id for item in interests}
    if {a.pk, b.pk} <= senders:
        return "Mutual interest (both sent)"
    if senders:
        return "One member sent an interest"
    return "No interest yet"


class ReviewEventInline(TabularInline):
    model = ReviewEvent
    extra = 0
    can_delete = False
    fields = ["created_at", "review_status", "staff", "note"]
    readonly_fields = fields
    verbose_name_plural = "Review history"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class MutualFilter(admin.SimpleListFilter):
    title = "compatibility"
    parameter_name = "compatibility"

    def lookups(self, request, model_admin):
        return [("mutual", "Mutually compatible"), ("one_sided", "One-sided")]

    def queryset(self, request, queryset):
        reverse_current = MatchRecommendation.objects.filter(
            member=OuterRef("candidate"), candidate=OuterRef("member"), status=RecommendationStatus.ACTIVE
        )
        if self.value() == "mutual":
            return queryset.filter(Exists(reverse_current), status=RecommendationStatus.ACTIVE)
        if self.value() == "one_sided":
            return queryset.exclude(Exists(reverse_current))
        return queryset


class VisibleFilter(admin.SimpleListFilter):
    title = "visible to the member"
    parameter_name = "visible"

    def lookups(self, request, model_admin):
        return [("yes", "Visible"), ("no", "Not visible")]

    def queryset(self, request, queryset):
        visible = engine.member_visible_q() & Q(status=RecommendationStatus.ACTIVE)
        if self.value() == "yes":
            return queryset.filter(visible)
        if self.value() == "no":
            return queryset.exclude(visible)
        return queryset


class DismissForm(forms.Form):
    reason = forms.CharField(max_length=300, widget=forms.Textarea(attrs={"rows": 3}),
                             help_text="Kept in the review history. Members never see it.")


@admin.register(MatchRecommendation)
class MatchRecommendationAdmin(ModelAdmin):
    """Auto-matched profiles: one row per direction, "candidate suits member's preferences"."""

    list_display = [
        "member_ref", "candidate_ref", "score", "compatibility", "status", "review_status", "visible",
        "first_generated_at", "last_evaluated_at",
    ]
    list_filter = ["status", "review_status", MutualFilter, VisibleFilter, "algorithm_version",
                   ("first_generated_at", admin.DateFieldListFilter)]
    list_select_related = ["member", "candidate"]
    search_fields = ["member__profile_code", "member__display_name", "candidate__profile_code", "candidate__display_name"]
    search_help_text = "Search by either member's Matrimony ID or name."
    ordering = ["member__profile_code", "-score", "candidate_id"]
    list_per_page = 50
    actions = ["approve", "dismiss", "flag", "refresh", "regenerate_members"]
    inlines = [ReviewEventInline]
    fieldsets = [
        (None, {"fields": ["member_ref", "candidate_ref", "status", "algorithm_version", "first_generated_at",
                           "last_evaluated_at"]}),
        ("Why (from the member's own preferences)", {"fields": ["score", "reasons_list", "mismatched_list",
                                                                  "not_stated_list"]}),
        ("Both directions", {"fields": ["other_direction", "compatibility", "interests"]}),
        ("Review", {"fields": ["review_status", "visible", "reviewed_by", "reviewed_at", "review_note",
                               "hidden_by_member_at"]}),
    ]

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields] + [
            "member_ref", "candidate_ref", "reasons_list", "mismatched_list", "not_stated_list", "other_direction",
            "compatibility", "interests", "visible",
        ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_review_permission(self, request):
        return request.user.has_perm(REVIEW)

    def has_generate_permission(self, request):
        return request.user.has_perm(GENERATE)

    def get_queryset(self, request):
        reverse_current = MatchRecommendation.objects.filter(
            member=OuterRef("candidate"), candidate=OuterRef("member"), status=RecommendationStatus.ACTIVE
        )
        return super().get_queryset(request).annotate(reverse_current=Exists(reverse_current))

    # --- Columns -----------------------------------------------------------------

    @admin.display(description="Member", ordering="member__profile_code")
    def member_ref(self, rec):
        return profile_link(rec.member)

    @admin.display(description="Recommended profile", ordering="candidate__profile_code")
    def candidate_ref(self, rec):
        return profile_link(rec.candidate)

    @admin.display(description="Compatibility")
    def compatibility(self, rec):
        current = getattr(rec, "reverse_current", None)
        if current is None:
            current = MatchRecommendation.objects.filter(
                member=rec.candidate, candidate=rec.member, status=RecommendationStatus.ACTIVE).exists()
        return "Mutual" if current and rec.status == RecommendationStatus.ACTIVE else "One-sided"

    @admin.display(description="Visible to member", boolean=True)
    def visible(self, rec):
        return engine.is_visible(rec)

    @admin.display(description="Matched preferences")
    def reasons_list(self, rec):
        return bullet_list(rec.reasons)

    @admin.display(description="Preferences not met")
    def mismatched_list(self, rec):
        return bullet_list(rec.mismatched)

    @admin.display(description="Not stated by the candidate (lowers confidence)")
    def not_stated_list(self, rec):
        return bullet_list(rec.not_stated)

    @admin.display(description="The other direction")
    def other_direction(self, rec):
        other = MatchRecommendation.objects.filter(member=rec.candidate, candidate=rec.member).first()
        if other is None:
            met = "meets" if rec.reverse_must_haves_met else "doesn't meet"
            return f"Not evaluated yet. The member {met} the candidate's must-haves."
        return format_html(
            '<a href="{}">Score {} for {}</a> ({}). Matched: {}',
            reverse("admin:matchmaking_matchrecommendation_change", args=[other.pk]),
            other.score if other.score is not None else "—", other.member.profile_code,
            other.get_status_display(), ", ".join(other.reasons) or "nothing",
        )

    @admin.display(description="Interests")
    def interests(self, rec):
        return interest_state(rec.member, rec.candidate)

    # --- Actions -------------------------------------------------------------------

    @admin.action(description="Approve for display", permissions=["review"])
    def approve(self, request, queryset):
        count = engine.review(list(queryset), request.user, ReviewStatus.APPROVED)
        self.message_user(request, f"Approved {count}. Only current recommendations can be approved.")

    @admin.action(description="Flag for further review", permissions=["review"])
    def flag(self, request, queryset):
        count = engine.review(list(queryset), request.user, ReviewStatus.FLAGGED, "Flagged from the list.")
        self.message_user(request, f"Flagged {count}. Flagged recommendations aren't shown to members.")

    @admin.action(description="Dismiss with a reason…", permissions=["review"])
    def dismiss(self, request, queryset):
        form = DismissForm(request.POST if request.POST.get("confirmed") == "yes" else None)
        if form.is_bound and form.is_valid():
            count = engine.review(list(queryset), request.user, ReviewStatus.DISMISSED, form.cleaned_data["reason"])
            self.message_user(request, f"Dismissed {count}.")
            return None
        return TemplateResponse(request, "admin/matchmaking/confirm.html", {
            **self.admin_site.each_context(request), "title": "Dismiss recommendations", "opts": self.model._meta,
            "objects": queryset, "form": form, "action": "dismiss", "button": "Dismiss",
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "intro": "Dismissed recommendations are never shown to the member, even after a refresh.",
        })

    @admin.action(description="Refresh selected (re-evaluate their members)", permissions=["generate"])
    def refresh(self, request, queryset):
        members = Profile.objects.filter(pk__in=queryset.values("member_id"))
        record = engine.run(members, "admin_refresh", request.user)
        self.message_user(request, run_message(record))

    @admin.action(description="Regenerate all matches for these members…", permissions=["generate"])
    def regenerate_members(self, request, queryset):
        members = Profile.objects.filter(pk__in=queryset.values("member_id"))
        if request.POST.get("confirmed") == "yes":
            record = engine.run(members, "admin", request.user)
            self.message_user(request, run_message(record))
            return None
        return TemplateResponse(request, "admin/matchmaking/confirm.html", {
            **self.admin_site.each_context(request), "title": "Regenerate matches", "opts": self.model._meta,
            "objects": queryset, "action": "regenerate_members", "button": f"Regenerate for {members.count()} member(s)",
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "intro": "Each member's recommendations are re-evaluated from their current preferences. Review "
                     "decisions stay unless the data changed (then they go back to review, if review is required).",
        })

    # --- Extra pages ------------------------------------------------------------------

    def get_urls(self):
        return [
            path("analytics/", self.admin_site.admin_view(self.analytics_view), name="matchmaking_analytics"),
            path("generate/", self.admin_site.admin_view(self.generate_view), name="matchmaking_generate"),
            *super().get_urls(),
        ]

    def analytics_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        start = parse_date(request.GET.get("from"))
        end = parse_date(request.GET.get("to"), end=True)
        context = {
            **self.admin_site.each_context(request),
            "title": "Matchmaking analytics", "opts": self.model._meta,
            "figures": engine.analytics(start, end), "period": (request.GET.get("from", ""), request.GET.get("to", "")),
            "incomplete": engine.incomplete_preference_members().order_by("profile_code")[:50],
            "review_required": engine.review_required(),
            "can_generate": self.has_generate_permission(request),
        }
        return TemplateResponse(request, "admin/matchmaking/analytics.html", context)

    def generate_view(self, request):
        """Generate for given Matrimony IDs, stale recommendations only, or every eligible member."""
        if not self.has_generate_permission(request):
            raise PermissionDenied
        if request.method == "POST":
            scope = request.POST.get("scope")
            if scope == "ids":
                codes = [code.strip().upper() for code in request.POST.get("codes", "").replace(",", " ").split() if code.strip()]
                members = engine.eligible_members().filter(profile_code__in=codes)
            elif scope == "stale":
                members = engine.eligible_members().filter(
                    pk__in=MatchRecommendation.objects.filter(status=RecommendationStatus.STALE).values("member_id"))
            elif scope == "all" and request.POST.get("confirm_all") == "yes":
                members = engine.eligible_members()
            else:
                messages.error(request, "Choose what to generate (and tick the confirmation for every member).")
                return redirect("admin:matchmaking_generate")
            record = engine.run(members, f"admin_{scope}", request.user)
            self.message_user(request, run_message(record))
            return redirect("admin:matchmaking_analytics")
        return TemplateResponse(request, "admin/matchmaking/generate.html", {
            **self.admin_site.each_context(request), "title": "Generate matches", "opts": self.model._meta,
            "eligible": engine.eligible_members().count(),
            "stale": MatchRecommendation.objects.filter(status=RecommendationStatus.STALE).values("member_id").distinct().count(),
        })


def run_message(record: MatchRun) -> str:
    failures = f", {record.failures} failed (see the log)" if record.failures else ""
    return (f"Evaluated {record.members_evaluated} member(s): {record.created} new, {record.updated} updated, "
            f"{record.unchanged} unchanged, {record.withdrawn} no longer matches{failures}.")


def parse_date(value, end=False):
    try:
        day = datetime.strptime(value or "", "%Y-%m-%d").date()
    except ValueError:
        return None
    moment = timezone.make_aware(datetime.combine(day, time.min))
    return moment + timedelta(days=1) if end else moment


@admin.register(PendingRecommendation)
class ReviewQueueAdmin(MatchRecommendationAdmin):
    """Current recommendations awaiting review, and flagged ones."""

    list_filter = ["review_status", MutualFilter, ("first_generated_at", admin.DateFieldListFilter)]
    actions = ["approve", "dismiss", "flag"]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            Q(review_status=ReviewStatus.PENDING, status=RecommendationStatus.ACTIVE) | Q(review_status=ReviewStatus.FLAGGED)
        )

    def get_urls(self):
        return super(MatchRecommendationAdmin, self).get_urls()


@admin.register(MutualMatch)
class MutualMatchAdmin(ModelAdmin):
    """Pairs where each member's profile meets the other's must-haves (both directions current)."""

    list_display = ["low_ref", "high_ref", "low_score", "high_score", "interest", "mutual_since"]
    list_select_related = ["profile_low", "profile_high", "low_to_high", "high_to_low"]
    search_fields = ["profile_low__profile_code", "profile_high__profile_code", "profile_low__display_name",
                     "profile_high__display_name"]
    search_help_text = "Search by either member's Matrimony ID or name."
    list_filter = [("mutual_since", admin.DateFieldListFilter)]
    ordering = ["-mutual_since", "-pk"]

    def get_queryset(self, request):
        def sent(sender, receiver):
            return Exists(Interest.objects.filter(sender=OuterRef(sender), receiver=OuterRef(receiver))
                          .exclude(status=InterestStatus.WITHDRAWN))

        accepted = Interest.objects.filter(status=InterestStatus.ACCEPTED).filter(
            Q(sender=OuterRef("profile_low"), receiver=OuterRef("profile_high"))
            | Q(sender=OuterRef("profile_high"), receiver=OuterRef("profile_low"))
        )
        # Interest states in the same query as the list (no query per row).
        return super().get_queryset(request).filter(mutual=True).annotate(
            low_sent=sent("profile_low", "profile_high"), high_sent=sent("profile_high", "profile_low"),
            accepted=Exists(accepted),
        )

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in MatchPair._meta.fields] + ["interest"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Member A", ordering="profile_low__profile_code")
    def low_ref(self, pair):
        return profile_link(pair.profile_low)

    @admin.display(description="Member B", ordering="profile_high__profile_code")
    def high_ref(self, pair):
        return profile_link(pair.profile_high)

    @admin.display(description="B for A's preferences")
    def low_score(self, pair):
        return pair.low_to_high.score if pair.low_to_high and pair.low_to_high.score is not None else "—"

    @admin.display(description="A for B's preferences")
    def high_score(self, pair):
        return pair.high_to_low.score if pair.high_to_low and pair.high_to_low.score is not None else "—"

    @admin.display(description="Interests (separate from compatibility)")
    def interest(self, pair):
        if not hasattr(pair, "accepted"):
            return interest_state(pair.profile_low, pair.profile_high)
        if pair.accepted:
            return "Interest accepted"
        if pair.low_sent and pair.high_sent:
            return "Mutual interest (both sent)"
        return "One member sent an interest" if pair.low_sent or pair.high_sent else "No interest yet"


@admin.register(MatchRun)
class MatchRunAdmin(ModelAdmin):
    list_display = ["started_at", "trigger", "triggered_by", "members_evaluated", "created", "updated", "unchanged",
                    "withdrawn", "failures", "finished_at"]
    list_filter = ["trigger"]
    ordering = ["-started_at"]

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in MatchRun._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
