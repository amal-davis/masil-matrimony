"""
Matchmaking assistance: Gold/Diamond assistance requests and the Platinum
assisted-matchmaking service. Both are AssistanceRequest cases, handled by
staff in the admin; this module holds every rule, so the admin and the member
API can't disagree.

Gold and Diamond ("Dedicated Matchmaking Assistance, subject to service availability")
  The member asks from the membership page (request_assistance). One open
  request at a time. While MATCHMAKING_ASSISTANCE_AVAILABLE is off nobody can ask.

Platinum ("Assisted Matchmaking")
  The case is opened by the activation of a Platinum membership itself
  (open_service_case, called by the admin's "Activate" action and by
  apps.payments when Razorpay confirms the payment), once per membership,
  "Awaiting assignment" until staff assign a matchmaker. Its service period is
  the membership's period. On top of the request workflow a Platinum case has:
  - personalised search: the matchmaker searches from the member's saved
    partner preferences (apps.profiles.matching) or with search filters
    (apps.profiles.search), as that member, in the admin; never with contact
    details. Profiles they pick are recorded as suggestions (AssistanceCandidate)
    and shown to the member only when staff share them; the member answers
    "interested" or "not interested" themselves.
  - interest management: staff see the member's real interests (read-only) and
    record follow-ups. Nobody sends, accepts or declines an interest for a member.
  - contact coordination (ContactExchange): the matchmaker proposes an exchange
    of mobile numbers with one other member, stating the purpose. Each member
    is shown exactly what will be shared and why, and decides. Numbers are
    shown to the two of them only once both consented; a decline or a
    withdrawal before then ends it, and nothing is disclosed. Paying for
    Platinum is never consent. No number is stored on these records.
  - follow-ups (AssistanceFollowUp) and notes (AssistanceNote): internal unless
    staff tick "shown to member".

Who may do what
  - Members see only their own cases, and only member-visible fields
    (never staff notes, internal follow-up outcomes or staff contact details).
    They can't assign, change status or edit notes: there is no API for it.
  - Staff with "Can see every matchmaking case and assign matchmakers"
    (memberships.assign_assistancerequest) see every case and assign matchmakers.
  - Other staff who may change cases (matchmakers) see and work on only the
    cases assigned to them.
  - A matchmaker must be an active staff account allowed to change cases.

Royal ("Exclusive At-Home Matchmaking")
  Everything Platinum has, on a 12-month case opened the same way, plus:
  - a service plan: the member's own requirements (member_note, which they may
    update) kept apart from the staff's agreed plan and next steps (both shown
    to the member), on top of their saved partner preferences (never changed here);
  - Royal stages (requirements gathering, profile curation, awaiting member
    review, family coordination, consultation requested/scheduled). A case can
    be "Consultation scheduled" only with a confirmed consultation, and "Family
    coordination" only with a family contact the member permitted;
  - at-home consultations (Consultation): requested by the member (or recorded
    by staff for them); staff propose a date and time; it is scheduled only
    when the member confirms; staff may reschedule (back to "proposed"), record
    it as unavailable, cancel it, or record the outcome once it has taken place.
    Nothing is scheduled automatically. The visit address is restricted to the
    case's staff; member APIs only say whether one was given;
  - family coordination (FamilyContact): only the member grants permission
    for a named relative, for a stated purpose, and may withdraw it. Staff may
    suggest a contact (it waits for the member's permission) and record
    coordination actions only while permission is granted.
  Suggested profiles are re-checked for eligibility when shared and whenever
  shown; one no longer visible shows as "no longer available" with no details.

When the membership ends (expiry, or staff cancelling it, e.g. after a refund)
  The case and all its records are kept. The member still sees it. Nothing new
  that depends on the service can happen: no new suggestions shared, no new
  contact exchanges, and pending exchanges can't be consented to. Staff close
  the case themselves (Completed, Cancelled or Expired); nothing is marked
  completed automatically. Continuing service after expiry needs a business
  rule that doesn't exist yet.
"""
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import NotificationKind
from apps.notifications.services import notify

from .entitlements import Feature, current_subscription, entitlements_for, feature_available
from .models import (
    ASSIGNED_STATUSES,
    OPEN_ASSISTANCE_STATUSES,
    OPEN_CONSULTATION_STATUSES,
    AssistanceCandidate,
    AssistanceEvent,
    AssistanceKind,
    AssistanceRequest,
    AssistanceStatus,
    CandidateResponse,
    ConsentDecision,
    ContactConsent,
    ContactExchange,
    Consultation,
    ConsultationEvent,
    ConsultationStatus,
    ExchangeStatus,
    FamilyContact,
    FamilyCoordination,
    FamilyPermission,
    FollowUpStatus,
)
from .plans import PackageCode

# Packages whose activation opens an assisted-matchmaking case.
SERVICE_CASE_PACKAGES = frozenset({PackageCode.PLATINUM, PackageCode.ROYAL})
# The at-home service: consultations, family coordination and the Royal stages.
HOME_SERVICE_PACKAGES = frozenset({PackageCode.ROYAL})
ROYAL_STATUSES = frozenset({
    AssistanceStatus.REQUIREMENTS, AssistanceStatus.CURATION, AssistanceStatus.AWAITING_REVIEW,
    AssistanceStatus.FAMILY, AssistanceStatus.CONSULTATION_REQUESTED, AssistanceStatus.CONSULTATION_SCHEDULED,
})
HANDLE_PERM = "memberships.change_assistancerequest"
ASSIGN_PERM = "memberships.assign_assistancerequest"

MEMBER_TITLES = {
    AssistanceStatus.ASSIGNED: "A matchmaker has been assigned to you",
    AssistanceStatus.IN_PROGRESS: "Your matchmaker is working on your request",
    AssistanceStatus.AWAITING_MEMBER: "Your matchmaker is waiting for your response",
    AssistanceStatus.FOLLOW_UP: "Your matchmaker has scheduled a follow-up",
    AssistanceStatus.ON_HOLD: "Your matchmaking case is on hold",
    AssistanceStatus.COMPLETED: "Your matchmaking request is complete",
    AssistanceStatus.UNAVAILABLE: "Matchmaking assistance isn't available for your request",
    AssistanceStatus.CANCELLED: "Your matchmaking case was cancelled",
    AssistanceStatus.EXPIRED: "Your matchmaking service period has ended",
    AssistanceStatus.REQUIREMENTS: "Your matchmaker is gathering your requirements",
    AssistanceStatus.CURATION: "Your matchmaker is curating profiles for you",
    AssistanceStatus.AWAITING_REVIEW: "Profiles are ready for your review",
    AssistanceStatus.FAMILY: "Your matchmaker is coordinating with your family",
    AssistanceStatus.CONSULTATION_REQUESTED: "Your consultation request is being arranged",
    AssistanceStatus.CONSULTATION_SCHEDULED: "Your consultation is scheduled",
}


class AssistanceError(Exception):
    def __init__(self, message, code, status=409, feature=None):
        super().__init__(message)
        self.message, self.code, self.status, self.feature = message, code, status, feature


def member_link(item: AssistanceRequest) -> str:
    return "/dashboard/matchmaking" if item.kind == AssistanceKind.SERVICE else "/dashboard/membership"


def is_home_service(item: AssistanceRequest) -> bool:
    return item.kind == AssistanceKind.SERVICE and item.subscription.plan_code in HOME_SERVICE_PACKAGES


def case_features(item: AssistanceRequest) -> dict:
    """What this case's package includes beyond updates, follow-ups and suggestions."""
    home = is_home_service(item)
    return {"contact_exchange": item.kind == AssistanceKind.SERVICE, "consultations": home, "family": home}


def status_problem(item: AssistanceRequest, status: str) -> str | None:
    """Why a case can't be put in `status` (so it never claims what wasn't recorded), or None."""
    if status in ROYAL_STATUSES and not is_home_service(item):
        return "That stage belongs to the Royal service."
    if status == AssistanceStatus.CONSULTATION_SCHEDULED and not item.consultations.filter(
        status=ConsultationStatus.SCHEDULED
    ).exists():
        return "No consultation has been confirmed by the member yet."
    if status == AssistanceStatus.FAMILY and not item.family_contacts.filter(permission=FamilyPermission.GRANTED).exists():
        return "The member hasn't permitted coordination with any family member."
    if status == AssistanceStatus.EXPIRED and item.service_active:
        return "The membership's service period hasn't ended."
    return None


# --- Staff permissions -----------------------------------------------------------------


def can_handle_cases(user) -> bool:
    """May be assigned cases and work on them."""
    return bool(user and user.is_active and user.is_staff and user.has_perm(HANDLE_PERM))


def can_assign(user) -> bool:
    """Sees every case and assigns matchmakers."""
    return bool(user and user.is_active and user.is_staff and user.has_perm(ASSIGN_PERM))


def cases_for_staff(user, queryset=None):
    queryset = AssistanceRequest.objects.all() if queryset is None else queryset
    return queryset if can_assign(user) else queryset.filter(assigned_to=user)


def may_work_on(user, item: AssistanceRequest) -> bool:
    return can_assign(user) or (can_handle_cases(user) and item.assigned_to_id == user.pk)


def _require_worker(user, item):
    if not may_work_on(user, item):
        raise ValueError("You can only work on cases assigned to you.")


# --- Opening cases -----------------------------------------------------------------------


def request_assistance(user, note: str = "") -> AssistanceRequest:
    """A Gold or Diamond member asks for help."""
    from apps.profiles.choices import ProfileStatus

    with transaction.atomic():
        # Locking the membership row serialises a member's requests, so two at once can't both pass.
        entitlements = entitlements_for(user, lock=True)
        if not entitlements.has(Feature.MATCHMAKING_ASSISTANCE):
            raise AssistanceError("", code="upgrade_required", status=403, feature=Feature.MATCHMAKING_ASSISTANCE)
        if not feature_available(Feature.MATCHMAKING_ASSISTANCE):
            raise AssistanceError(
                "Matchmaking assistance is currently unavailable. Please try again later or contact us.",
                code="service_unavailable", status=403,
            )
        profile = getattr(user, "profile", None)
        if profile is None or profile.status != ProfileStatus.ACTIVE:
            raise AssistanceError(
                "Your profile must be approved before a matchmaker can help.", code="profile_not_active", status=403
            )
        if AssistanceRequest.objects.filter(user=user, status__in=OPEN_ASSISTANCE_STATUSES).exists():
            raise AssistanceError("You already have an open matchmaking request.", code="already_requested")
        item = AssistanceRequest.objects.create(
            user=user, subscription=entitlements.subscription, member_note=note.strip()[:1000]
        )
        AssistanceEvent.objects.create(request=item, status=item.status, changed_by=user)
    return item


def open_service_case(subscription, by=None) -> AssistanceRequest | None:
    """
    Open the assisted-matchmaking case of a just-activated Platinum membership.
    Call inside the activation's transaction. Idempotent: one case per membership.
    """
    if subscription.plan_code not in SERVICE_CASE_PACKAGES:
        return None
    existing = AssistanceRequest.objects.filter(subscription=subscription, kind=AssistanceKind.SERVICE).first()
    if existing is not None:
        return existing
    item = AssistanceRequest.objects.create(kind=AssistanceKind.SERVICE, user=subscription.user, subscription=subscription)
    AssistanceEvent.objects.create(request=item, status=item.status, changed_by=by)
    notify(
        subscription.user,
        NotificationKind.ASSISTANCE_UPDATED,
        "Your assisted matchmaking service has started",
        "We'll let you know when your matchmaker is assigned.",
        member_link(item),
    )
    return item


# --- Staff changes ---------------------------------------------------------------------


def staff_update(item: AssistanceRequest, staff_user, *, status: str, assigned_to=None, member_message: str = "") -> bool:
    """
    Record a staff change of status and/or matchmaker. Returns False when nothing
    changed. Raises ValueError for a change that isn't allowed.
    """
    with transaction.atomic():
        locked = AssistanceRequest.objects.select_for_update().select_related("subscription").get(pk=item.pk)
        if not locked.is_open:
            raise ValueError("This case is closed. The member can make a new request.")
        _require_worker(staff_user, locked)
        if assigned_to != locked.assigned_to and not can_assign(staff_user):
            raise ValueError("Only staff who assign cases can change the matchmaker.")
        if assigned_to is not None and not can_handle_cases(assigned_to):
            raise ValueError("Assign an active staff account that is allowed to handle matchmaking cases.")
        # Assigning someone to a waiting case moves it on.
        if status == AssistanceStatus.REQUESTED and assigned_to is not None:
            status = AssistanceStatus.ASSIGNED
        if status in ASSIGNED_STATUSES and assigned_to is None:
            raise ValueError("Assign a matchmaker first.")
        if status == AssistanceStatus.REQUESTED and locked.status != AssistanceStatus.REQUESTED:
            raise ValueError("A case can't go back to awaiting assignment; change the matchmaker instead.")
        if status != locked.status:
            problem = status_problem(locked, status)
            if problem:
                raise ValueError(problem)
        if status == locked.status and assigned_to == locked.assigned_to and member_message == locked.member_message:
            return False

        now = timezone.now()
        changed = status != locked.status or assigned_to != locked.assigned_to
        if assigned_to != locked.assigned_to:
            locked.assigned_at = now if assigned_to else None
        locked.assigned_to = assigned_to
        locked.status = status
        locked.member_message = member_message[:300]
        if status not in OPEN_ASSISTANCE_STATUSES:
            locked.closed_at = now
        locked.save()
        if changed:
            AssistanceEvent.objects.create(request=locked, status=status, assigned_to=assigned_to, changed_by=staff_user)
            notify(
                locked.user,
                NotificationKind.ASSISTANCE_UPDATED,
                MEMBER_TITLES.get(status, "Your matchmaking case was updated"),
                locked.member_message[:300],
                member_link(locked),
            )
    item.refresh_from_db()
    return True


def note_saved(note, staff_user, created: bool, was_visible: bool):
    """After a staff note is saved: a note that has just become visible is a progress update for the member."""
    if note.visible_to_member and (created or not was_visible):
        notify(note.request.user, NotificationKind.ASSISTANCE_UPDATED, "New update from your matchmaker",
               note.body[:300], member_link(note.request))


def follow_up_saved(follow_up, staff_user, created: bool, was_visible: bool):
    if follow_up.status == FollowUpStatus.DONE and follow_up.completed_at is None:
        follow_up.completed_at = timezone.now()
        follow_up.save(update_fields=["completed_at", "updated_at"])
    if follow_up.visible_to_member and (created or not was_visible):
        when = f" on {follow_up.due_on:%d %b %Y}" if follow_up.due_on else ""
        notify(follow_up.request.user, NotificationKind.ASSISTANCE_UPDATED, "Your matchmaker scheduled a follow-up",
               f"{follow_up.action}{when}"[:300], member_link(follow_up.request))


def candidate_problem(item: AssistanceRequest, profile) -> str | None:
    """Why `profile` can't be suggested to the case member, or None."""
    from apps.profiles.models import Profile
    from apps.profiles.search import searchable_gender

    member = getattr(item.user, "profile", None)
    if member is None:
        return "The member has no profile."
    if profile.pk == member.pk:
        return "That is the member's own profile."
    if profile.gender != searchable_gender(member):
        return "Suggest profiles of the gender the member is looking for."
    if not Profile.objects.discoverable().filter(pk=profile.pk).exists():
        return "That profile isn't approved and visible to members."
    return None


def add_candidates(item: AssistanceRequest, staff_user, profiles) -> int:
    """Record profiles found in the matchmaker's search as suggestions (not yet shown to the member)."""
    _require_worker(staff_user, item)
    added = 0
    for profile in profiles:
        if candidate_problem(item, profile) is None:
            _, created = AssistanceCandidate.objects.get_or_create(
                request=item, profile=profile, defaults={"added_by": staff_user}
            )
            added += created
    return added


def candidate_status(candidate) -> str:
    """recommended, shared, interested, declined, or no_longer_available (re-checked every time)."""
    if candidate_problem(candidate.request, candidate.profile) is not None:
        return "no_longer_available"
    if not candidate.shared_with_member:
        return "recommended"
    return {CandidateResponse.INTERESTED: "interested", CandidateResponse.NOT_INTERESTED: "declined"}.get(
        candidate.member_response, "shared"
    )


def candidate_saved(candidate, was_shared: bool):
    """After staff save a suggestion: sharing it shows it to the member (only while the service runs)."""
    if candidate.shared_with_member and not was_shared:
        candidate.shared_at = timezone.now()
        candidate.save(update_fields=["shared_at", "updated_at"])
        notify(candidate.request.user, NotificationKind.ASSISTANCE_UPDATED, "Your matchmaker suggested a profile",
               "Have a look and tell your matchmaker what you think.", member_link(candidate.request))


def respond_to_candidate(user, case_id, profile_code: str, response: str) -> AssistanceCandidate:
    if response not in (CandidateResponse.INTERESTED, CandidateResponse.NOT_INTERESTED):
        raise AssistanceError("Choose interested or not interested.", code="invalid", status=400)
    with transaction.atomic():
        candidate = (
            AssistanceCandidate.objects.select_for_update()
            .filter(request__public_id=case_id, request__user=user, profile__profile_code=profile_code,
                    shared_with_member=True)
            .first()
        )
        if candidate is None:
            raise AssistanceError("Suggestion not found.", code="not_found", status=404)
        candidate.member_response = response
        candidate.responded_at = timezone.now()
        candidate.save(update_fields=["member_response", "responded_at", "updated_at"])
    return candidate


# --- Contact exchange ---------------------------------------------------------------------

SHARED_INFO = "mobile number"


def _statement(other, purpose: str) -> str:
    return (
        f"Share my {SHARED_INFO} with {other.display_name} ({other.profile_code}), and see theirs, "
        f"through the Massil Matrimony matchmaking service. Purpose: {purpose}"
    )


def exchange_problem(item: AssistanceRequest, other_profile, staff_user, purpose: str) -> str | None:
    """Why this exchange can't be proposed, or None."""
    from apps.profiles.choices import ProfileStatus

    if not may_work_on(staff_user, item):
        return "You can only work on cases assigned to you."
    if item.kind != AssistanceKind.SERVICE:
        return "Contact exchange through a matchmaker is part of the Platinum service."
    if not item.is_open or not item.service_active:
        return "The case is closed or its service period has ended."
    if not purpose:
        return "Say why the numbers would be shared; both members see it."
    member = getattr(item.user, "profile", None)
    if member is None or member.status != ProfileStatus.ACTIVE:
        return "The member's profile isn't approved."
    problem = candidate_problem(item, other_profile)
    if problem:
        return problem
    if ContactExchange.objects.filter(
        request=item, other_profile=other_profile, status__in=(ExchangeStatus.PENDING, ExchangeStatus.SHARED)
    ).exists():
        return "An exchange with this member is already pending or done."
    return None


def clean_purpose(purpose: str) -> str:
    return " ".join((purpose or "").split())[:300]


def start_exchange(item: AssistanceRequest, other_profile, staff_user, purpose: str) -> ContactExchange:
    """The matchmaker proposes exchanging mobile numbers between the case member and `other_profile`."""
    purpose = clean_purpose(purpose)
    with transaction.atomic():
        locked = AssistanceRequest.objects.select_for_update().select_related("user__profile", "subscription").get(pk=item.pk)
        problem = exchange_problem(locked, other_profile, staff_user, purpose)
        if problem:
            raise ValueError(problem)
        member = locked.user.profile
        exchange = ContactExchange.objects.create(
            request=locked, other_profile=other_profile, purpose=purpose, initiated_by=staff_user
        )
        ContactConsent.objects.create(exchange=exchange, profile=member, statement=_statement(other_profile, purpose))
        ContactConsent.objects.create(exchange=exchange, profile=other_profile, statement=_statement(member, purpose))
        for profile in (member, other_profile):
            notify(profile.user, NotificationKind.CONTACT_EXCHANGE, "A matchmaker asks for your consent",
                   "Decide whether to exchange mobile numbers.", "/dashboard/contact-requests")
    return exchange


def cancel_exchange(exchange: ContactExchange, staff_user) -> bool:
    with transaction.atomic():
        locked = ContactExchange.objects.select_for_update().select_related("request").get(pk=exchange.pk)
        _require_worker(staff_user, locked.request)
        if locked.status != ExchangeStatus.PENDING:
            return False
        locked.status = ExchangeStatus.CANCELLED
        locked.cancelled_by = staff_user
        locked.closed_at = timezone.now()
        locked.save(update_fields=["status", "cancelled_by", "closed_at", "updated_at"])
    return True


def decide_consent(user, exchange_id, decision: str) -> ContactExchange:
    """A member grants, declines or withdraws their consent to an exchange they are part of."""
    profile = getattr(user, "profile", None)
    with transaction.atomic():
        exchange = (
            ContactExchange.objects.select_for_update().select_related("request__subscription")
            .filter(public_id=exchange_id, consents__profile=profile).first()
            if profile is not None else None
        )
        if exchange is None:
            raise AssistanceError("Request not found.", code="not_found", status=404)
        consent = exchange.consents.select_for_update().get(profile=profile)
        if exchange.status != ExchangeStatus.PENDING:
            raise AssistanceError("This request is no longer open.", code="closed")
        now = timezone.now()
        if decision == "grant":
            if consent.decision != ConsentDecision.PENDING:
                raise AssistanceError("You've already decided.", code="already_decided")
            if not exchange.request.service_active:
                raise AssistanceError("The matchmaking service period for this request has ended.", code="service_ended")
            consent.decision = ConsentDecision.GRANTED
        elif decision == "decline":
            if consent.decision != ConsentDecision.PENDING:
                raise AssistanceError("You've already decided.", code="already_decided")
            consent.decision = ConsentDecision.DECLINED
        elif decision == "withdraw":
            if consent.decision != ConsentDecision.GRANTED:
                raise AssistanceError("There is no consent to withdraw.", code="not_granted")
            consent.decision = ConsentDecision.WITHDRAWN
        else:
            raise AssistanceError("Choose grant, decline or withdraw.", code="invalid", status=400)
        consent.decided_at = now
        consent.save(update_fields=["decision", "decided_at"])

        others = [c for c in exchange.consents.all() if c.pk != consent.pk]
        if consent.decision == ConsentDecision.GRANTED and all(c.decision == ConsentDecision.GRANTED for c in others):
            exchange.status, exchange.shared_at = ExchangeStatus.SHARED, now
            title = "Mobile numbers exchanged"
        elif consent.decision in (ConsentDecision.DECLINED, ConsentDecision.WITHDRAWN):
            exchange.status, exchange.closed_at = ExchangeStatus.DECLINED, now
            title = "A contact exchange won't go ahead"
        else:
            title = None
        if title:
            exchange.save(update_fields=["status", "shared_at", "closed_at", "updated_at"])
            for item in [consent, *others]:
                notify(item.profile.user, NotificationKind.CONTACT_EXCHANGE, title, "", "/dashboard/contact-requests")
    return exchange


def exchange_data(exchange: ContactExchange, viewer, request) -> dict:
    """
    One exchange as `viewer` (a party) sees it. The other member's mobile number
    is included only once both consented, and showing it is recorded.
    """
    from apps.profiles.serializers import card_data

    consents = {c.profile_id: c for c in exchange.consents.all()}
    mine = consents[viewer.pk]
    other_consent = next(c for pk, c in consents.items() if pk != viewer.pk)
    other = other_consent.profile
    data = {
        "id": str(exchange.public_id),
        "status": exchange.status,
        "status_label": exchange.get_status_display(),
        "purpose": exchange.purpose,
        "statement": mine.statement,
        "shares": SHARED_INFO,
        "my_decision": mine.decision,
        "created_at": exchange.created_at,
        "shared_at": exchange.shared_at,
        "profile": card_data(viewer, other, request),
        "phone_number": None,
    }
    if exchange.status == ExchangeStatus.SHARED:
        data["phone_number"] = other.user.phone_number
        if mine.number_seen_at is None:
            ContactConsent.objects.filter(pk=mine.pk, number_seen_at__isnull=True).update(number_seen_at=timezone.now())
    return data


def exchanges_for(profile):
    return (
        ContactExchange.objects.filter(consents__profile=profile)
        .select_related("request")
        .prefetch_related("consents__profile__user")
        .order_by("-created_at")
    )


# --- Member views -----------------------------------------------------------------------


def request_data(item: AssistanceRequest) -> dict:
    """What the member sees of a case. Never internal notes or a staff member's contact details."""
    matchmaker = item.assigned_to
    subscription = item.subscription
    return {
        "id": str(item.public_id),
        "kind": item.kind,
        "status": item.status,
        "status_label": item.get_status_display(),
        "is_open": item.is_open,
        "member_note": item.member_note,
        "requested_at": item.created_at,
        "assigned": matchmaker is not None,
        # First name only, and only once someone is actually assigned.
        "matchmaker_name": (matchmaker.first_name.strip() or "A Massil matchmaker") if matchmaker else None,
        "assigned_at": item.assigned_at,
        "closed_at": item.closed_at,
        "message": item.member_message,
        "service_active": item.service_active,
        "service_starts_at": subscription.starts_at,
        "service_ends_at": subscription.ends_at,
        "package_code": subscription.plan_code,
    }


def case_detail(item: AssistanceRequest, request) -> dict:
    from apps.profiles.serializers import card_data

    member = getattr(item.user, "profile", None)
    candidates = item.candidates.filter(shared_with_member=True).select_related("profile__user")
    features = case_features(item)
    return {
        **request_data(item),
        "features": features,
        # The member's own words, then the staff's agreed plan: kept apart.
        "requirements": item.member_note,
        "service_plan": item.service_plan,
        "next_steps": item.next_steps,
        "consultations": [consultation_data(c) for c in item.consultations.all()] if features["consultations"] else [],
        "family": [family_data(f) for f in item.family_contacts.prefetch_related("actions")] if features["family"] else [],
        "updates": [
            {"body": note.body, "created_at": note.created_at}
            for note in item.notes.filter(visible_to_member=True).order_by("-created_at")
        ],
        "follow_ups": [
            {
                "action": follow_up.action,
                "due_on": follow_up.due_on,
                "status": follow_up.status,
                "status_label": follow_up.get_status_display(),
                "awaiting_member": follow_up.awaiting_member,
            }
            for follow_up in item.follow_ups.filter(visible_to_member=True)
        ],
        "suggestions": [suggestion_data(candidate, member, request, card_data) for candidate in candidates]
        if member is not None else [],
        "exchanges": [exchange_data(exchange, member, request) for exchange in exchanges_for(member).filter(request=item)]
        if member is not None else [],
    }


def assistance_data(user) -> dict:
    entitlements = entitlements_for(user)
    current = current_subscription(user)
    items = AssistanceRequest.objects.filter(user=user).select_related("assigned_to", "subscription")[:5]
    return {
        # The current membership includes assistance: requested (Gold, Diamond) or as the service itself (Platinum).
        "included": entitlements.has(Feature.MATCHMAKING_ASSISTANCE)
        or (current is not None and current.plan_code in SERVICE_CASE_PACKAGES),
        "can_request": entitlements.has(Feature.MATCHMAKING_ASSISTANCE),
        "available": feature_available(Feature.MATCHMAKING_ASSISTANCE),
        "requests": [request_data(item) for item in items],
    }


def suggestion_data(candidate, member, request, card_data) -> dict:
    status = candidate_status(candidate)
    gone = status == "no_longer_available"
    return {
        # No details of a profile that is no longer visible.
        "profile": None if gone else card_data(member, candidate.profile, request),
        "status": status,
        "shared_at": candidate.shared_at,
        "response": candidate.member_response,
    }


# --- Royal: service plan --------------------------------------------------------------


def member_case(user, case_id, lock=False) -> AssistanceRequest:
    queryset = AssistanceRequest.objects.select_related("subscription", "user__profile")
    if lock:
        queryset = queryset.select_for_update()
    item = queryset.filter(public_id=case_id, user=user).first()
    if item is None:
        raise AssistanceError("Not found.", code="not_found", status=404)
    return item


def update_requirements(user, case_id, text: str) -> AssistanceRequest:
    """The member updates their own requirements on their service case (never staff fields)."""
    with transaction.atomic():
        item = member_case(user, case_id, lock=True)
        if item.kind != AssistanceKind.SERVICE or not item.is_open:
            raise AssistanceError("This case can't be changed.", code="closed")
        item.member_note = (text or "").strip()[:1000]
        item.member_note_updated_at = timezone.now()
        item.save(update_fields=["member_note", "member_note_updated_at", "updated_at"])
    return item


# --- Royal: at-home consultations --------------------------------------------------------


def consultation_data(consultation) -> dict:
    """What the member sees: never the address itself or the internal outcome."""
    return {
        "id": str(consultation.public_id),
        "status": consultation.status,
        "status_label": consultation.get_status_display(),
        "member_note": consultation.member_note,
        "location_provided": bool(consultation.address),
        "scheduled_for": consultation.scheduled_for,
        "confirmed_at": consultation.confirmed_at,
        "completed_at": consultation.completed_at,
        "message": consultation.member_message,
        "requested_at": consultation.created_at,
    }


def _consultation_event(consultation, by):
    ConsultationEvent.objects.create(
        consultation=consultation, status=consultation.status, scheduled_for=consultation.scheduled_for, changed_by=by
    )


def _home_case_problem(item) -> str | None:
    if not is_home_service(item):
        return "At-home consultations are part of the Royal service."
    if not item.is_open or not item.service_active:
        return "The case is closed or its service period has ended."
    return None


def request_consultation(item: AssistanceRequest, by, note: str = "", address: str = "") -> Consultation:
    """Record a consultation request: by the member, or by staff on the member's behalf."""
    with transaction.atomic():
        locked = AssistanceRequest.objects.select_for_update().select_related("subscription").get(pk=item.pk)
        problem = _home_case_problem(locked)
        if problem:
            raise AssistanceError(problem, code="not_available", status=403)
        if by != locked.user and not may_work_on(by, locked):
            raise AssistanceError("You can only work on cases assigned to you.", code="forbidden", status=403)
        if locked.consultations.filter(status__in=OPEN_CONSULTATION_STATUSES).exists():
            raise AssistanceError("A consultation is already being arranged.", code="already_requested")
        consultation = Consultation.objects.create(
            request=locked, requested_by=by, member_note=(note or "").strip()[:500], address=(address or "").strip()[:500]
        )
        _consultation_event(consultation, by)
    return consultation


def staff_consultation(consultation, staff_user, action: str, *, when=None, message: str = "", outcome: str = "") -> Consultation:
    """
    Staff actions: "propose" (a date and time; also reschedules), "unavailable",
    "cancel" or "complete" (only for a scheduled visit whose time has passed).
    Raises ValueError when not allowed.
    """
    with transaction.atomic():
        locked = Consultation.objects.select_for_update().select_related("request__subscription").get(pk=consultation.pk)
        _require_worker(staff_user, locked.request)
        now = timezone.now()
        if action == "propose":
            if not locked.is_open:
                raise ValueError("This consultation is closed.")
            if when is None or when <= now:
                raise ValueError("Propose a date and time in the future.")
            if not locked.request.service_active:
                raise ValueError("The service period has ended.")
            locked.status, locked.scheduled_for, locked.confirmed_at = ConsultationStatus.PROPOSED, when, None
            title = "Please confirm your consultation time"
        elif action in ("unavailable", "cancel"):
            if not locked.is_open:
                raise ValueError("This consultation is closed.")
            locked.status = ConsultationStatus.UNAVAILABLE if action == "unavailable" else ConsultationStatus.CANCELLED
            title = "Your consultation won't go ahead" if action == "cancel" else "A home visit isn't available"
        elif action == "complete":
            if locked.status != ConsultationStatus.SCHEDULED or locked.scheduled_for is None or locked.scheduled_for > now:
                raise ValueError("Only a confirmed consultation whose time has passed can be recorded as completed.")
            locked.status, locked.completed_at = ConsultationStatus.COMPLETED, now
            title = "Your consultation is recorded as completed"
        else:
            raise ValueError("Unknown action.")
        locked.member_message = message[:300]
        if outcome:
            locked.outcome = outcome
        locked.save()
        _consultation_event(locked, staff_user)
        notify(locked.request.user, NotificationKind.ASSISTANCE_UPDATED, title, locked.member_message,
               member_link(locked.request))
    return locked


def member_consultation(user, case_id, consultation_id, action: str) -> Consultation:
    """The member confirms a proposed time (only then is it scheduled) or cancels."""
    with transaction.atomic():
        item = member_case(user, case_id)
        consultation = item.consultations.select_for_update().filter(public_id=consultation_id).first()
        if consultation is None:
            raise AssistanceError("Not found.", code="not_found", status=404)
        if action == "confirm":
            if consultation.status != ConsultationStatus.PROPOSED:
                raise AssistanceError("There is no proposed time to confirm.", code="nothing_to_confirm")
            if consultation.scheduled_for <= timezone.now() or not item.service_active:
                raise AssistanceError("That time has passed or the service has ended. Ask for a new time.", code="expired")
            consultation.status, consultation.confirmed_at = ConsultationStatus.SCHEDULED, timezone.now()
        elif action == "cancel":
            if not consultation.is_open:
                raise AssistanceError("This consultation is closed.", code="closed")
            consultation.status = ConsultationStatus.CANCELLED
        else:
            raise AssistanceError("Choose confirm or cancel.", code="invalid", status=400)
        consultation.save()
        _consultation_event(consultation, user)
    return consultation


# --- Royal: family coordination ----------------------------------------------------------


def _family_statement(contact) -> str:
    return (
        f"I permit my Massil Matrimony matchmaker to contact {contact.name} ({contact.relationship}) "
        f"for this purpose only: {contact.purpose}. I can withdraw this permission at any time."
    )


def _masked(number: str) -> str:
    digits = "".join(ch for ch in number if ch.isdigit())
    return f"•••• {digits[-4:]}" if len(digits) >= 4 else ""


def family_data(contact) -> dict:
    """The member's own record: the number is masked; internal outcomes are never included."""
    return {
        "id": str(contact.public_id),
        "name": contact.name,
        "relationship": contact.relationship,
        "phone_hint": _masked(contact.phone_number),
        "purpose": contact.purpose,
        "permission": contact.permission,
        "permission_label": contact.get_permission_display(),
        "statement": contact.statement or _family_statement(contact),
        "granted_at": contact.granted_at,
        "withdrawn_at": contact.withdrawn_at,
        "actions": [
            {"action": action.action, "created_at": action.created_at}
            for action in contact.actions.all() if action.visible_to_member
        ],
    }


def add_family_contact(item: AssistanceRequest, by, *, name, relationship, phone_number="", purpose) -> FamilyContact:
    """
    By the member: recorded with their permission (their explicit act). By staff:
    waits for the member's permission. Nothing is coordinated before it's granted.
    """
    name, relationship, purpose = name.strip()[:80], relationship.strip()[:40], " ".join(purpose.split())[:300]
    if not (name and relationship and purpose):
        raise AssistanceError("Give a name, the relationship and the purpose.", code="invalid", status=400)
    with transaction.atomic():
        locked = AssistanceRequest.objects.select_for_update().select_related("subscription").get(pk=item.pk)
        problem = None if is_home_service(locked) else "Family coordination is part of the Royal service."
        if problem is None and not (locked.is_open and locked.service_active):
            problem = "The case is closed or its service period has ended."
        if problem:
            raise AssistanceError(problem, code="not_available", status=403)
        by_member = by == locked.user
        if not by_member and not may_work_on(by, locked):
            raise AssistanceError("You can only work on cases assigned to you.", code="forbidden", status=403)
        contact = FamilyContact(
            request=locked, name=name, relationship=relationship, phone_number=phone_number.strip()[:20],
            purpose=purpose, added_by=by,
        )
        if by_member:
            contact.permission, contact.granted_at = FamilyPermission.GRANTED, timezone.now()
            contact.statement = _family_statement(contact)
        contact.save()
        if not by_member:
            notify(locked.user, NotificationKind.ASSISTANCE_UPDATED, "Your matchmaker asks for your permission",
                   f"To coordinate with {name} ({relationship}).", member_link(locked))
    return contact


def decide_family(user, case_id, contact_id, decision: str) -> FamilyContact:
    with transaction.atomic():
        item = member_case(user, case_id)
        contact = item.family_contacts.select_for_update().filter(public_id=contact_id).first()
        if contact is None:
            raise AssistanceError("Not found.", code="not_found", status=404)
        now = timezone.now()
        if decision == "grant":
            if contact.permission == FamilyPermission.GRANTED:
                raise AssistanceError("Already permitted.", code="already_decided")
            if not (item.is_open and item.service_active):
                raise AssistanceError("The service period has ended.", code="service_ended")
            contact.permission, contact.granted_at, contact.withdrawn_at = FamilyPermission.GRANTED, now, None
            contact.statement = _family_statement(contact)
        elif decision == "withdraw":
            if contact.permission == FamilyPermission.WITHDRAWN:
                raise AssistanceError("Already withdrawn.", code="already_decided")
            contact.permission, contact.withdrawn_at = FamilyPermission.WITHDRAWN, now
        else:
            raise AssistanceError("Choose grant or withdraw.", code="invalid", status=400)
        contact.save()
    return contact


def family_action_problem(contact, staff_user) -> str | None:
    if not may_work_on(staff_user, contact.request):
        return "You can only work on cases assigned to you."
    if contact.permission != FamilyPermission.GRANTED:
        return "The member hasn't permitted coordination with this person (or withdrew permission)."
    if not (contact.request.is_open and contact.request.service_active):
        return "The case is closed or its service period has ended."
    return None


def record_family_action(contact, staff_user, action: str, outcome: str = "", visible: bool = False) -> FamilyCoordination:
    with transaction.atomic():
        locked = FamilyContact.objects.select_for_update().select_related("request__subscription").get(pk=contact.pk)
        problem = family_action_problem(locked, staff_user)
        if problem:
            raise ValueError(problem)
        return FamilyCoordination.objects.create(
            contact=locked, action=action.strip()[:300], outcome=outcome, visible_to_member=visible, staff=staff_user
        )
