from django import forms
from django.contrib import admin
from django.contrib.admin import helpers
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin

from apps.notifications.models import NotificationKind
from apps.notifications.services import notify

from . import assistance
from .models import (
    ASSIGNED_STATUSES,
    AssistanceCandidate,
    AssistanceEvent,
    AssistanceFollowUp,
    AssistanceKind,
    AssistanceNote,
    AssistanceRequest,
    AssistanceStatus,
    Consultation,
    ContactConsent,
    ContactExchange,
    FamilyContact,
    FamilyCoordination,
    FamilyPermission,
    MembershipPackage,
    Subscription,
    SubscriptionStatus,
)


def rupees(value) -> str:
    return "—" if value is None else f"₹{value:,.2f}"


@admin.register(MembershipPackage)
class MembershipPackageAdmin(ModelAdmin):
    """
    The six packages. The set is fixed (entitlement rules key off the codes), so
    packages can't be added or deleted here. Staff with change permission edit the
    copy and availability; fees, tax, validity and limits need the separate
    "Can change package terms" permission, which only superusers have by default.
    Edits apply to subscriptions recorded afterwards: existing subscriptions keep
    the fee, validity and contact limit they were recorded with.
    """

    list_display = [
        "name", "code", "category", "fee_display", "tax_treatment", "validity_display",
        "contact_view_limit", "outgoing_interest_limit", "is_available", "display_order",
    ]
    list_filter = ["category", "is_available", "tax_treatment"]
    search_fields = ["name", "code"]
    ordering = ["display_order", "pk"]
    fieldsets = [
        (None, {"fields": ["code", "category", "is_available", "display_order"]}),
        ("Fees and tax", {
            "fields": ["fee", "fee_label", "tax_treatment", "stated_gst_rate", "gst_display", "total_display"],
        }),
        ("Validity and limits", {"fields": ["validity_months", "contact_view_limit", "outgoing_interest_limit"]}),
        ("Website copy", {"fields": [
            "name", "subtitle", "tagline", "service_label", "description", "benefits", "terms_title", "terms_body",
            "cta_label",
        ]}),
        ("Record", {"fields": ["created_at", "updated_at"]}),
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        fields = ["code", "gst_display", "total_display", "created_at", "updated_at"]
        if not request.user.has_perm("memberships.change_package_terms"):
            fields += list(MembershipPackage.COMMERCIAL_FIELDS)
        return fields

    @admin.display(description="Fee (excl. GST)", ordering="fee")
    def fee_display(self, package):
        return rupees(package.fee)

    @admin.display(description="Validity")
    def validity_display(self, package):
        return f"{package.validity_months} months" if package.validity_months else "No expiry"

    @admin.display(description="GST amount")
    def gst_display(self, package):
        return rupees(package.gst_amount) if package.gst_amount is not None else "Applicable GST, added at payment"

    @admin.display(description="Total payable")
    def total_display(self, package):
        total = package.total_payable
        return rupees(total) if total is not None else "Fee plus applicable GST (no GST rate is configured)"


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    """
    Staff record a subscription after confirming an offline payment, then use
    "Activate" to start its validity period. Online purchases create their
    subscription themselves once Razorpay confirms the payment (Membership
    Purchases in the sidebar).
    """

    list_display = ["user", "matrimony_id", "plan_code", "status", "starts_at", "ends_at", "created_at"]
    list_filter = ["plan_code", "status"]
    list_select_related = ["user__profile"]
    search_fields = ["user__email", "user__phone_number", "user__profile__profile_code"]
    search_help_text = "Search by email, mobile number or Matrimony ID."
    ordering = ["-created_at"]
    list_per_page = 50
    autocomplete_fields = ["user"]
    # Status changes only through the actions below, so the validity period and
    # the member's notification are always set correctly. The package terms are
    # copied from the package when the subscription is recorded, and contact views
    # are counted by the contact-access API, so staff can't edit either.
    readonly_fields = [
        "public_id", "status", "starts_at", "ends_at", "package_fee", "validity_months", "contact_view_limit",
        "contact_views_used", "activated_by", "created_at", "updated_at",
    ]
    fieldsets = [
        (None, {"fields": ["public_id", "user", "plan_code", "status"]}),
        ("Terms when recorded", {"fields": ["package_fee", "validity_months", "contact_view_limit"]}),
        ("Validity", {"fields": ["starts_at", "ends_at", "contact_views_used"]}),
        ("Staff", {"fields": ["staff_note", "activated_by", "created_at", "updated_at"]}),
    ]
    actions = ["activate", "cancel"]

    def get_readonly_fields(self, request, obj=None):
        # The package can't change after recording: its terms were copied then.
        return [*self.readonly_fields, "user", "plan_code"] if obj else self.readonly_fields

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "plan_code":
            available = set(MembershipPackage.objects.available().values_list("code", flat=True))
            kwargs["choices"] = [("", "---------")] + [c for c in db_field.choices if c[0] in available]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    @admin.display(description="Matrimony ID", ordering="user__profile__profile_code")
    def matrimony_id(self, subscription):
        profile = getattr(subscription.user, "profile", None)
        if profile is None:
            return "—"
        return format_html(
            '<a href="{}">{}</a>', reverse("admin:profiles_profile_change", args=[profile.pk]), profile.profile_code
        )

    @admin.action(description="Cancel selected subscriptions", permissions=["change"])
    def cancel(self, request, queryset):
        to_cancel = list(queryset.exclude(status=SubscriptionStatus.CANCELLED).select_related("user"))
        if not to_cancel:
            self.message_user(request, "The selected subscriptions are already cancelled.")
            return None
        # Cancelling ends a member's benefits, so ask first.
        if request.POST.get("confirmed") != "yes":
            return TemplateResponse(
                request,
                "admin/memberships/subscription/cancel_confirmation.html",
                {
                    **self.admin_site.each_context(request),
                    "title": "Cancel subscriptions",
                    "opts": self.model._meta,
                    "subscriptions": to_cancel,
                    "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                },
            )
        with transaction.atomic():
            for subscription in to_cancel:
                subscription.status = SubscriptionStatus.CANCELLED
                subscription.save(update_fields=["status", "updated_at"])
                self.log_change(request, subscription, "Cancelled from the subscription list.")
        self.message_user(request, f"Cancelled {len(to_cancel)} subscription(s).")
        return None

    @admin.action(description="Activate selected subscriptions (payment confirmed)", permissions=["change"])
    def activate(self, request, queryset):
        count = 0
        with transaction.atomic():
            for subscription in queryset.select_for_update().filter(status=SubscriptionStatus.PENDING):
                subscription.activate(by=request.user)
                subscription.save()
                # Platinum: the assisted-matchmaking case starts with the membership.
                assistance.open_service_case(subscription, by=request.user)
                notify(
                    subscription.user,
                    NotificationKind.MEMBERSHIP_ACTIVATED,
                    f"Your {subscription.plan.name} is active",
                    f"Valid until {subscription.ends_at:%d %b %Y}.",
                    "/dashboard/membership",
                )
                self.log_change(request, subscription, "Activated after payment was confirmed.")
                count += 1
        self.message_user(request, f"Activated {count} subscription(s). Only pending subscriptions are changed.")


class CaseInlineMixin:
    """Inlines of a case: only staff who may work on that case can add or change them. Nothing is deleted."""

    extra = 0

    def _may(self, request, obj):
        return obj is not None and assistance.may_work_on(request.user, obj)

    def has_add_permission(self, request, obj=None):
        return self._may(request, obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._may(request, obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


class AssistanceEventInline(admin.TabularInline):
    model = AssistanceEvent
    extra = 0
    can_delete = False
    fields = ["created_at", "status", "assigned_to", "changed_by"]
    readonly_fields = fields
    verbose_name_plural = "Status and assignment history"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class AssistanceNoteInline(CaseInlineMixin, admin.StackedInline):
    model = AssistanceNote
    fields = ["body", "visible_to_member", "author", "created_at"]
    readonly_fields = ["author", "created_at"]
    verbose_name_plural = "Notes and member updates (unticked notes are internal)"


class AssistanceFollowUpInline(CaseInlineMixin, admin.TabularInline):
    model = AssistanceFollowUp
    fields = ["action", "due_on", "status", "awaiting_member", "visible_to_member", "outcome", "created_by", "completed_at"]
    readonly_fields = ["created_by", "completed_at"]


class CandidateForm(forms.ModelForm):
    class Meta:
        model = AssistanceCandidate
        fields = ["profile", "shared_with_member", "staff_note"]

    def clean(self):
        cleaned = super().clean()
        item, profile = self.instance.request, cleaned.get("profile")
        if profile is not None and (self.instance.pk is None or "profile" in self.changed_data):
            problem = assistance.candidate_problem(item, profile)
            if problem:
                self.add_error("profile", problem)
        if cleaned.get("shared_with_member") and "shared_with_member" in self.changed_data:
            if not item.service_active:
                self.add_error("shared_with_member", "The member's service period has ended.")
            elif profile is not None:
                # Re-checked at the moment of sharing: the profile may have been hidden since it was found.
                problem = assistance.candidate_problem(item, profile)
                if problem:
                    self.add_error("shared_with_member", problem)
        return cleaned


class AssistanceCandidateInline(CaseInlineMixin, admin.TabularInline):
    model = AssistanceCandidate
    form = CandidateForm
    raw_id_fields = ["profile"]
    fields = ["profile", "shared_with_member", "status", "member_response", "staff_note", "added_by", "shared_at"]
    readonly_fields = ["status", "member_response", "added_by", "shared_at"]

    @admin.display(description="Status")
    def status(self, candidate):
        if candidate.pk is None:
            return "—"
        return assistance.candidate_status(candidate).replace("_", " ").capitalize()
    verbose_name_plural = "Suggested profiles (found with “Find matches”, shown to the member once shared)"


class ContactExchangeInline(admin.TabularInline):
    model = ContactExchange
    extra = 0
    can_delete = False
    fields = ["other_profile", "purpose", "status", "initiated_by", "created_at", "shared_at"]
    readonly_fields = fields
    verbose_name_plural = "Contact exchanges (proposed under Matchmaking › Contact exchanges)"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ConsultationInline(admin.TabularInline):
    """Read-only here; arrange each consultation from its own page (Consultations)."""

    model = Consultation
    extra = 0
    can_delete = False
    fields = ["status", "scheduled_for", "confirmed_at", "completed_at", "manage"]
    readonly_fields = fields
    verbose_name_plural = "At-home consultations (arrange them under Matchmaking › Consultations)"

    @admin.display(description="")
    def manage(self, consultation):
        return format_html('<a class="underline" href="{}">Open</a>',
                           reverse("admin:memberships_consultation_change", args=[consultation.pk]))

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class FamilyContactInline(CaseInlineMixin, admin.TabularInline):
    """Staff may suggest a family contact; only the member can permit coordination with them."""

    model = FamilyContact
    fields = ["name", "relationship", "phone_number", "purpose", "permission", "granted_at", "withdrawn_at"]
    readonly_fields = ["permission", "granted_at", "withdrawn_at"]
    verbose_name_plural = (
        "Family coordination (the member grants or withdraws permission in their dashboard; once recorded, "
        "only the phone number can be corrected here)"
    )


class AssistanceRequestForm(forms.ModelForm):
    class Meta:
        model = AssistanceRequest
        fields = ["status", "assigned_to", "member_message", "service_plan", "next_steps", "staff_note"]

    def clean(self):
        cleaned = super().clean()
        instance = self.instance
        status = cleaned.get("status", instance.status)
        assignee = cleaned.get("assigned_to", instance.assigned_to)
        if instance.pk and not instance.is_open and (status != instance.status or assignee != instance.assigned_to):
            raise forms.ValidationError("This case is closed. The member can make a new request.")
        if status in ASSIGNED_STATUSES and not assignee:
            self.add_error(None, "Assign a matchmaker first.")
        if "assigned_to" in cleaned and assignee is not None and not assistance.can_handle_cases(assignee):
            self.add_error("assigned_to", "This account isn't allowed to handle matchmaking cases.")
        if status == AssistanceStatus.REQUESTED and instance.status != AssistanceStatus.REQUESTED:
            self.add_error("status", "A case can't go back to awaiting assignment; change the matchmaker instead.")
        if status != instance.status:
            problem = assistance.status_problem(instance, status)
            if problem:
                self.add_error("status", problem)
        return cleaned


@admin.register(AssistanceRequest)
class AssistanceRequestAdmin(ModelAdmin):
    """
    Matchmaking cases (apps.memberships.assistance): Gold and Diamond members'
    assistance requests, and Platinum members' assisted-matchmaking service,
    opened when the membership is activated.

    Staff who may assign cases see every case and choose the matchmaker. Other
    staff (matchmakers) see only the cases assigned to them. Status and
    matchmaker changes are kept in the history and the member is notified.
    Notes and follow-ups are internal unless "shown to member" is ticked.
    Nothing here sends, accepts or declines an interest for a member.
    """

    form = AssistanceRequestForm
    list_display = ["matrimony_id", "kind", "status", "assigned_to", "service_until", "created_at"]
    list_filter = ["kind", "status", "assigned_to"]
    list_select_related = ["user__profile", "assigned_to", "subscription"]
    search_fields = ["user__profile__profile_code", "user__email", "user__phone_number"]
    search_help_text = "Search by Matrimony ID, email or mobile number."
    ordering = ["-created_at"]
    readonly_fields = [
        "public_id", "kind", "member", "membership_validity", "member_note", "preferences_summary",
        "interests_overview", "find_matches", "assigned_at", "closed_at", "created_at", "updated_at",
    ]
    fieldsets = [
        (None, {"fields": ["public_id", "kind", "member", "membership_validity", "created_at"]}),
        ("Handling", {"fields": ["status", "assigned_to", "assigned_at", "member_message", "closed_at"]}),
        ("Service plan", {
            "description": "The member's own requirements (they can update them) are kept apart from the plan "
            "and next steps you agree, which the member sees.",
            "fields": ["member_note", "service_plan", "next_steps"],
        }),
        ("Partner preferences and search", {"fields": ["preferences_summary", "find_matches"]}),
        ("Interests (read-only)", {"fields": ["interests_overview"]}),
        ("Staff", {"fields": ["staff_note", "updated_at"]}),
    ]
    inlines = [AssistanceNoteInline, AssistanceFollowUpInline, AssistanceCandidateInline, ContactExchangeInline,
               ConsultationInline, FamilyContactInline, AssistanceEventInline]

    def get_inline_instances(self, request, obj=None):
        # Consultations and family coordination exist only on Royal cases.
        home = obj is not None and assistance.is_home_service(obj)
        return [
            inline for inline in super().get_inline_instances(request, obj)
            if home or not isinstance(inline, (ConsultationInline, FamilyContactInline))
        ]
    actions = ["assign_to_me"]

    def get_queryset(self, request):
        return assistance.cases_for_staff(request.user, super().get_queryset(request))

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if not assistance.can_assign(request.user):
            fields.append("assigned_to")
        return fields

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj)
        return allowed and (obj is None or assistance.may_work_on(request.user, obj))

    def has_assign_permission(self, request):
        return assistance.can_assign(request.user)

    # --- Read-only panels ------------------------------------------------------------

    @admin.display(description="Matrimony ID", ordering="user__profile__profile_code")
    def matrimony_id(self, item):
        profile = getattr(item.user, "profile", None)
        return profile.profile_code if profile else "—"

    @admin.display(description="Service until", ordering="subscription__ends_at")
    def service_until(self, item):
        return f"{item.subscription.ends_at:%d %b %Y}" if item.subscription.ends_at else "—"

    @admin.display(description="Member")
    def member(self, item):
        profile = getattr(item.user, "profile", None)
        if profile is None:
            return "No profile"
        return format_html(
            '<a href="{}">{} ({})</a>', reverse("admin:profiles_profile_change", args=[profile.pk]),
            profile.display_name, profile.profile_code,
        )

    @admin.display(description="Membership")
    def membership_validity(self, item):
        subscription = item.subscription
        period = (
            f"{subscription.starts_at:%d %b %Y} – {subscription.ends_at:%d %b %Y}" if subscription.ends_at else "not active"
        )
        return f"{subscription.plan.name}, {subscription.display_status} ({period})"

    @admin.display(description="Saved partner preferences")
    def preferences_summary(self, item):
        from apps.profiles.matching import preference_of

        profile = getattr(item.user, "profile", None)
        pref = preference_of(profile) if profile else None
        if pref is None:
            return "The member hasn't saved partner preferences."
        rows = []
        for field in pref._meta.concrete_fields:
            if field.name in ("id", "profile", "created_at", "updated_at", "notes"):
                continue
            value = getattr(pref, field.name)
            if value not in (None, "", []):
                rows.append((field.verbose_name.capitalize(), ", ".join(value) if isinstance(value, list) else value))
        return format_html_join(mark_safe("<br>"), "<strong>{}</strong>: {}", rows) or "No preferences filled in."

    @admin.display(description="Member's interests")
    def interests_overview(self, item):
        from apps.interactions.models import Interest

        profile = getattr(item.user, "profile", None)
        if profile is None:
            return "—"
        interests = (
            Interest.objects.filter(Q(sender=profile) | Q(receiver=profile))
            .select_related("sender", "receiver").order_by("-updated_at")[:30]
        )
        rows = [
            ("Sent to" if interest.sender_id == profile.pk else "Received from",
             (interest.receiver if interest.sender_id == profile.pk else interest.sender).profile_code,
             interest.get_status_display(), f"{interest.updated_at:%d %b %Y}")
            for interest in interests
        ]
        if not rows:
            return "No interests sent or received yet."
        return format_html_join(mark_safe("<br>"), "{} {}: {} ({})", rows)

    @admin.display(description="Personalised search")
    def find_matches(self, item):
        if item.kind != AssistanceKind.SERVICE and not item.is_open:
            return "—"
        return format_html(
            '<a class="font-medium text-primary-600 underline" href="{}">Find matches for this member</a>',
            reverse("admin:memberships_assistancerequest_find_matches", args=[item.pk]),
        )

    # --- Saving ---------------------------------------------------------------------

    def save_model(self, request, obj, form, change):
        # Status and matchmaker go through the service, so history and notifications are always recorded.
        original = AssistanceRequest.objects.get(pk=obj.pk)
        AssistanceRequest.objects.filter(pk=obj.pk).update(
            staff_note=obj.staff_note, service_plan=obj.service_plan, next_steps=obj.next_steps
        )
        if original.is_open:
            try:
                assistance.staff_update(
                    original, request.user, status=obj.status, assigned_to=obj.assigned_to,
                    member_message=obj.member_message,
                )
            except ValueError as error:
                self.message_user(request, str(error), level="error")
        obj.refresh_from_db()

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        model = formset.model
        for instance in instances:
            created = instance.pk is None
            before = model.objects.filter(pk=instance.pk).first() if not created else None
            if model is AssistanceNote:
                if created:
                    instance.author = request.user
                instance.save()
                assistance.note_saved(instance, request.user, created, bool(before and before.visible_to_member))
            elif model is AssistanceFollowUp:
                if created:
                    instance.created_by = request.user
                instance.save()
                assistance.follow_up_saved(instance, request.user, created, bool(before and before.visible_to_member))
            elif model is AssistanceCandidate:
                if created:
                    instance.added_by = request.user
                instance.save()
                assistance.candidate_saved(instance, bool(before and before.shared_with_member))
            elif model is FamilyContact:
                if created:
                    # Staff can only suggest a contact: it waits for the member's permission.
                    try:
                        assistance.add_family_contact(
                            instance.request, request.user, name=instance.name, relationship=instance.relationship,
                            phone_number=instance.phone_number, purpose=instance.purpose,
                        )
                    except assistance.AssistanceError as error:
                        self.message_user(request, error.message, level="error")
                else:
                    FamilyContact.objects.filter(pk=instance.pk).update(phone_number=instance.phone_number)
            else:
                instance.save()
        formset.save_m2m()

    # --- Personalised search ----------------------------------------------------------

    def get_urls(self):
        return [
            path(
                "<int:object_id>/find-matches/",
                self.admin_site.admin_view(self.find_matches_view),
                name="memberships_assistancerequest_find_matches",
            ),
            *super().get_urls(),
        ]

    def find_matches_view(self, request, object_id):
        """
        Search for the case member, as that member: their saved preferences by
        default, or search filters. Same eligibility rules as the member's own
        matches and search; no contact details. Chosen profiles become
        suggestions on the case (not shown to the member until shared).
        """
        from apps.profiles import matching, search

        item = self.get_queryset(request).select_related("user__profile").filter(pk=object_id).first()
        if item is None or not self.has_change_permission(request, item):
            raise PermissionDenied
        member = getattr(item.user, "profile", None)
        if member is None:
            self.message_user(request, "The member has no profile to search for.", level="error")
            return redirect("admin:memberships_assistancerequest_change", item.pk)

        if request.method == "POST":
            from apps.profiles.models import Profile

            ids = [value for value in request.POST.getlist("profile") if value.isdigit()]
            added = assistance.add_candidates(item, request.user, Profile.objects.filter(pk__in=ids))
            self.message_user(request, f"Added {added} suggested profile(s). Share them with the member from the case page.")
            return redirect("admin:memberships_assistancerequest_change", item.pk)

        mode = "filters" if request.GET.get("mode") == "filters" else "preferences"
        errors = {}
        if mode == "filters":
            filters = search.SearchFilters.from_query(request.GET, context={"viewer": member})
            if filters.is_valid():
                results = search.search_profiles(member, filters.validated_data)
            else:
                errors, results = filters.errors, _no_profiles()
        else:
            results = matching.ranked_candidates(member)
        already = set(item.candidates.values_list("profile_id", flat=True))
        rows = [
            {
                "profile": profile,
                "score": matching.explain(member, profile).score,
                "suggested": profile.pk in already,
            }
            for profile in results.select_related("user", "partner_preference")[:50]
        ]
        context = {
            **self.admin_site.each_context(request),
            "title": f"Find matches for {member.display_name} ({member.profile_code})",
            "opts": self.model._meta,
            "case": item,
            "member": member,
            "mode": mode,
            "rows": rows,
            "errors": errors,
            "query": request.GET,
        }
        return TemplateResponse(request, "admin/memberships/assistancerequest/find_matches.html", context)

    @admin.action(description="Assign selected cases to me", permissions=["assign"])
    def assign_to_me(self, request, queryset):
        count = 0
        for item in queryset.filter(status=AssistanceStatus.REQUESTED):
            try:
                changed = assistance.staff_update(item, request.user, status=AssistanceStatus.ASSIGNED, assigned_to=request.user)
            except ValueError as error:
                self.message_user(request, str(error), level="error")
                return
            if changed:
                self.log_change(request, item, "Assigned to me.")
                count += 1
        self.message_user(request, f"Assigned {count} case(s) to you. Only cases awaiting assignment change.")


def _no_profiles():
    from apps.profiles.models import Profile

    return Profile.objects.none()


class ContactConsentInline(admin.TabularInline):
    model = ContactConsent
    extra = 0
    can_delete = False
    fields = ["profile", "decision", "decided_at", "number_seen_at", "statement"]
    readonly_fields = fields
    verbose_name_plural = "Consent of each member (numbers are shown to them only once both consented)"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ContactExchangeForm(forms.ModelForm):
    class Meta:
        model = ContactExchange
        fields = ["request", "other_profile", "purpose"]

    def __init__(self, *args, staff_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.staff_user = staff_user
        if "request" in self.fields:
            self.fields["request"].queryset = assistance.cases_for_staff(
                staff_user, AssistanceRequest.objects.filter(kind=AssistanceKind.SERVICE)
            ).select_related("user__profile")
            self.fields["request"].label = "Matchmaking case"

    def clean(self):
        cleaned = super().clean()
        item, other = cleaned.get("request"), cleaned.get("other_profile")
        if item is not None and other is not None:
            problem = assistance.exchange_problem(item, other, self.staff_user, assistance.clean_purpose(cleaned.get("purpose")))
            if problem:
                raise forms.ValidationError(problem)
        return cleaned


@admin.register(ContactExchange)
class ContactExchangeAdmin(ModelAdmin):
    """
    Exchanges of mobile numbers proposed by a matchmaker for a Platinum case.
    Both members are asked; the numbers are shown to them (never here) only once
    both consented. A decline or withdrawal before that ends the exchange.
    """

    form = ContactExchangeForm
    list_display = ["case_member", "other_member", "status", "initiated_by", "created_at", "shared_at"]
    list_filter = ["status"]
    list_select_related = ["request__user__profile", "other_profile", "initiated_by"]
    search_fields = ["request__user__profile__profile_code", "other_profile__profile_code"]
    search_help_text = "Search by either member's Matrimony ID."
    raw_id_fields = ["other_profile"]
    inlines = [ContactConsentInline]
    actions = ["cancel_pending"]

    def get_queryset(self, request):
        cases = assistance.cases_for_staff(request.user)
        return super().get_queryset(request).filter(request__in=cases)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        class Form(form):
            def __init__(self, *args, **inner):
                super().__init__(*args, staff_user=request.user, **inner)

        return Form

    def get_fields(self, request, obj=None):
        if obj is None:
            return ["request", "other_profile", "purpose"]
        return ["public_id", "request", "other_profile", "purpose", "status", "initiated_by", "created_at",
                "shared_at", "closed_at", "cancelled_by"]

    def get_readonly_fields(self, request, obj=None):
        return self.get_fields(request, obj) if obj else []

    def has_add_permission(self, request):
        return super().has_add_permission(request) and assistance.can_handle_cases(request.user)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Case member")
    def case_member(self, exchange):
        return getattr(exchange.request.user, "profile", None) and exchange.request.user.profile.profile_code

    @admin.display(description="Other member", ordering="other_profile__profile_code")
    def other_member(self, exchange):
        return exchange.other_profile.profile_code

    def save_model(self, request, obj, form, change):
        if change:
            return
        created = assistance.start_exchange(obj.request, obj.other_profile, request.user, obj.purpose)
        obj.pk, obj.public_id = created.pk, created.public_id

    @admin.action(description="Cancel selected pending exchanges", permissions=["change"])
    def cancel_pending(self, request, queryset):
        count = 0
        for exchange in queryset:
            try:
                count += assistance.cancel_exchange(exchange, request.user)
            except ValueError as error:
                self.message_user(request, str(error), level="error")
        self.message_user(request, f"Cancelled {count} exchange(s). Only pending exchanges change.")



class ConsultationActionForm(forms.ModelForm):
    """Add: record a request for the member. Change: propose/reschedule, mark unavailable, cancel or complete."""

    ACTIONS = [
        ("", "— No change —"),
        ("propose", "Propose a date and time (also reschedules; the member must confirm)"),
        ("unavailable", "Home visit unavailable"),
        ("cancel", "Cancel"),
        ("complete", "Record as completed (after the confirmed time)"),
    ]
    action = forms.ChoiceField(choices=ACTIONS, required=False)
    when = forms.DateTimeField(required=False, label="Proposed date and time (India time)")

    class Meta:
        model = Consultation
        fields = ["request", "member_note", "address", "member_message", "outcome"]

    def __init__(self, *args, staff_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.staff_user = staff_user
        if "request" in self.fields:
            self.fields["request"].queryset = assistance.cases_for_staff(
                staff_user, AssistanceRequest.objects.filter(kind=AssistanceKind.SERVICE, subscription__plan_code="royal")
            ).select_related("user__profile")
            self.fields["request"].label = "Royal case"

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and cleaned.get("action") == "propose" and not cleaned.get("when"):
            self.add_error("when", "Give the proposed date and time.")
        return cleaned


@admin.register(Consultation)
class ConsultationAdmin(ModelAdmin):
    """
    At-home consultations on Royal cases. Nothing is scheduled automatically: staff
    propose a time and it is scheduled only once the member confirms it in their
    dashboard. Every change is kept in the history. The address is visible only to
    staff who handle the case.
    """

    form = ConsultationActionForm
    list_display = ["case_member", "status", "scheduled_for", "confirmed_at", "created_at"]
    list_filter = ["status"]
    list_select_related = ["request__user__profile"]
    search_fields = ["request__user__profile__profile_code"]
    search_help_text = "Search by the member's Matrimony ID."
    inlines = []

    def get_queryset(self, request):
        return super().get_queryset(request).filter(request__in=assistance.cases_for_staff(request.user))

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["fields"] = ["request", "member_note", "address"]
        form = super().get_form(request, obj, **kwargs)

        class Form(form):
            def __init__(self, *args, **inner):
                super().__init__(*args, staff_user=request.user, **inner)

        return Form

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return [(None, {"fields": ["request", "member_note", "address"]})]
        return [
            (None, {"fields": ["case_member", "status", "scheduled_for", "confirmed_at", "completed_at", "member_note",
                               "address"]}),
            ("Next action", {"fields": ["action", "when", "member_message", "outcome"]}),
            ("History", {"fields": ["history"]}),
        ]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        return ["case_member", "status", "scheduled_for", "confirmed_at", "completed_at", "member_note", "history"]

    def has_add_permission(self, request):
        return super().has_add_permission(request) and assistance.can_handle_cases(request.user)

    def has_change_permission(self, request, obj=None):
        allowed = super().has_change_permission(request, obj)
        return allowed and (obj is None or assistance.may_work_on(request.user, obj.request))

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Member")
    def case_member(self, consultation):
        profile = getattr(consultation.request.user, "profile", None)
        return profile.profile_code if profile else "—"

    @admin.display(description="History")
    def history(self, consultation):
        rows = [
            (f"{event.created_at:%d %b %Y %H:%M}", event.get_status_display(),
             f" for {timezone.localtime(event.scheduled_for):%d %b %Y %H:%M}" if event.scheduled_for else "")
            for event in consultation.events.all()
        ]
        return format_html_join(mark_safe("<br>"), "{}: {}{}", rows) or "—"

    def save_model(self, request, obj, form, change):
        if not change:
            created = assistance.request_consultation(obj.request, request.user, obj.member_note, obj.address)
            obj.pk = created.pk
            return
        Consultation.objects.filter(pk=obj.pk).update(address=obj.address, outcome=obj.outcome)
        action = form.cleaned_data.get("action")
        if action:
            try:
                assistance.staff_consultation(
                    obj, request.user, action, when=form.cleaned_data.get("when"),
                    message=obj.member_message, outcome=obj.outcome,
                )
            except ValueError as error:
                self.message_user(request, str(error), level="error")
        obj.refresh_from_db()

    def save_related(self, request, form, formsets, change):
        if change:
            super().save_related(request, form, formsets, change)


class FamilyCoordinationForm(forms.ModelForm):
    class Meta:
        model = FamilyCoordination
        fields = ["contact", "action", "outcome", "visible_to_member"]

    def __init__(self, *args, staff_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.staff_user = staff_user
        if "contact" in self.fields:
            self.fields["contact"].queryset = FamilyContact.objects.filter(
                request__in=assistance.cases_for_staff(staff_user), permission=FamilyPermission.GRANTED
            ).select_related("request__user__profile")
            self.fields["contact"].label = "Family contact (only those the member permitted)"

    def clean(self):
        cleaned = super().clean()
        contact = cleaned.get("contact")
        if contact is not None:
            problem = assistance.family_action_problem(contact, self.staff_user)
            if problem:
                raise forms.ValidationError(problem)
        return cleaned


@admin.register(FamilyCoordination)
class FamilyCoordinationAdmin(ModelAdmin):
    """Coordination with a member's family: recorded only while the member's permission stands."""

    form = FamilyCoordinationForm
    list_display = ["contact", "action", "visible_to_member", "staff", "created_at"]
    list_select_related = ["contact", "staff"]
    search_fields = ["contact__request__user__profile__profile_code"]
    search_help_text = "Search by the member's Matrimony ID."

    def get_queryset(self, request):
        return super().get_queryset(request).filter(contact__request__in=assistance.cases_for_staff(request.user))

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        class Form(form):
            def __init__(self, *args, **inner):
                super().__init__(*args, staff_user=request.user, **inner)

        return Form

    def get_readonly_fields(self, request, obj=None):
        # A record of what happened: not edited afterwards.
        return ["contact", "action", "outcome", "visible_to_member", "staff", "created_at"] if obj else ["staff", "created_at"]

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            return
        created = assistance.record_family_action(
            obj.contact, request.user, obj.action, obj.outcome, obj.visible_to_member
        )
        obj.pk = created.pk
