from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsMember
from apps.interactions.services import free_interests_used
from apps.payments import razorpay_api

from . import assistance
from .entitlements import current_subscription, entitlements_for, upgrade_required
from .models import AssistanceRequest, MembershipPackage, Subscription


def money(value) -> str | None:
    """Rupee amounts as decimal strings ("12000.00"), so no precision is lost."""
    return None if value is None else f"{value:.2f}"


def package_data(package: MembershipPackage) -> dict:
    return {
        "code": package.code,
        "category": package.category,
        "name": package.name,
        "subtitle": package.subtitle,
        "tagline": package.tagline,
        "service_label": package.service_label,
        "description": package.description,
        "fee": money(package.fee),
        "fee_label": package.fee_label,
        "tax_treatment": package.tax_treatment,
        "stated_gst_rate": money(package.stated_gst_rate),
        # The rate the total uses (stated, or the configured applicable rate); None while unconfirmed.
        "gst_rate": money(package.gst_rate),
        "gst_amount": money(package.gst_amount),
        # None while it depends on an applicable GST rate that isn't configured (MEMBERSHIP_GST_RATE_PERCENT).
        "total_payable": money(package.total_payable),
        "validity_months": package.validity_months,
        "contact_view_limit": package.contact_view_limit,
        "outgoing_interest_limit": package.outgoing_interest_limit,
        "benefits": [{"title": item["title"], "detail": item.get("detail", "")} for item in package.benefits],
        "terms": {"title": package.terms_title, "body": package.terms_body},
        "cta_label": package.cta_label,
    }


class PackageListView(APIView):
    """The packages offered on the website, in display order. Public."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["memberships"])
    def get(self, request):
        return Response([package_data(item) for item in MembershipPackage.objects.available()])


def subscription_data(subscription: Subscription) -> dict:
    plan = subscription.plan
    return {
        "id": str(subscription.public_id),
        "plan_code": plan.code,
        "plan_name": plan.name,
        "status": subscription.display_status,
        "starts_at": subscription.starts_at,
        "ends_at": subscription.ends_at,
        "validity_months": subscription.validity_months,
        "package_fee": money(subscription.package_fee),
        "contact_view_limit": subscription.contact_view_limit,
        "contact_views_used": subscription.contact_views_used if subscription.contact_view_limit else None,
    }


def entitlements_data(user) -> dict:
    """What the member's membership allows now (memberships.entitlements), with their Free interest usage."""
    entitlements = entitlements_for(user)
    data = entitlements.as_dict()
    counted = entitlements.is_free and entitlements.outgoing_interest_limit is not None
    data["outgoing_interests_used"] = free_interests_used(getattr(user, "profile", None)) if counted else None
    return data


class MyMembershipView(APIView):
    """The member's current membership, what it allows, and their subscription history."""

    permission_classes = [IsMember]

    @extend_schema(tags=["memberships"])
    def get(self, request):
        current = current_subscription(request.user)
        history = Subscription.objects.filter(user=request.user).order_by("-created_at")
        return Response(
            {
                "current": subscription_data(current) if current else None,
                "history": [subscription_data(item) for item in history],
                "entitlements": entitlements_data(request.user),
                "assistance": assistance.assistance_data(request.user),
                # Razorpay checkout is configured (apps.payments). Whether a given package can be
                # bought is decided per package by GET /payments/checkout/<code>/.
                "online_payment_available": razorpay_api.configured(),
            }
        )


class AssistanceRequestInput(serializers.Serializer):
    note = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class MyAssistanceView(APIView):
    """
    GET: whether the member's membership includes matchmaking assistance, whether
    the service is available now, and their requests (newest first).
    POST {note}: ask for assistance (apps.memberships.assistance).
    """

    permission_classes = [IsMember]

    @extend_schema(tags=["memberships"])
    def get(self, request):
        return Response(assistance.assistance_data(request.user))

    @extend_schema(request=AssistanceRequestInput, tags=["memberships"])
    def post(self, request):
        data = AssistanceRequestInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            item = assistance.request_assistance(request.user, data.validated_data["note"])
        except assistance.AssistanceError as error:
            return assistance_error(error)
        return Response(assistance.request_data(item), status=status.HTTP_201_CREATED)


def private(response: Response) -> Response:
    """Case data and contact numbers are personal: never stored by shared caches."""
    response["Cache-Control"] = "private, no-store"
    return response


def assistance_error(error: assistance.AssistanceError) -> Response:
    body = upgrade_required(error.feature) if error.feature else {"detail": error.message, "code": error.code}
    return Response(body, status=error.status)


class MyAssistanceDetailView(APIView):
    """
    One of the member's own cases: status, matchmaker (once assigned), service
    period, progress updates and follow-ups staff chose to show, suggested
    profiles, and contact exchanges. Never internal notes. Another member's case
    is a 404.
    """

    permission_classes = [IsMember]

    @extend_schema(tags=["memberships"])
    def get(self, request, case_id):
        item = (
            AssistanceRequest.objects.select_related("assigned_to", "subscription", "user__profile")
            .filter(public_id=case_id, user=request.user)
            .first()
        )
        if item is None:
            return Response({"detail": "Not found.", "code": "not_found"}, status=status.HTTP_404_NOT_FOUND)
        return private(Response(assistance.case_detail(item, request)))


class SuggestionResponseInput(serializers.Serializer):
    response = serializers.ChoiceField(choices=["interested", "not_interested"])


class SuggestionResponseView(APIView):
    """POST {response}: the member tells their matchmaker what they think of a suggested profile."""

    permission_classes = [IsMember]

    @extend_schema(request=SuggestionResponseInput, tags=["memberships"])
    def post(self, request, case_id, profile_code):
        data = SuggestionResponseInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            candidate = assistance.respond_to_candidate(request.user, case_id, profile_code, data.validated_data["response"])
        except assistance.AssistanceError as error:
            return assistance_error(error)
        return private(Response({"response": candidate.member_response}))


class ContactExchangeListView(APIView):
    """
    GET: contact exchanges proposed by a matchmaker that involve the member, as
    either party. The other member's mobile number appears only once both consented.
    """

    permission_classes = [IsMember]

    @extend_schema(tags=["memberships"])
    def get(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None:
            return private(Response([]))
        return private(Response([assistance.exchange_data(item, profile, request) for item in assistance.exchanges_for(profile)]))


class ConsentInput(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["grant", "decline", "withdraw"])


class ContactExchangeDecisionView(APIView):
    """POST {decision}: grant, decline or withdraw consent to an exchange the member is part of."""

    permission_classes = [IsMember]
    throttle_scope = "contact_view"

    @extend_schema(request=ConsentInput, tags=["memberships"])
    def post(self, request, exchange_id):
        data = ConsentInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            exchange = assistance.decide_consent(request.user, exchange_id, data.validated_data["decision"])
        except assistance.AssistanceError as error:
            return assistance_error(error)
        return private(Response(assistance.exchange_data(exchange, request.user.profile, request)))


class RequirementsInput(serializers.Serializer):
    requirements = serializers.CharField(max_length=1000, allow_blank=True)


class MyCaseRequirementsView(APIView):
    """PATCH {requirements}: the member updates their own requirements on their service case."""

    permission_classes = [IsMember]

    @extend_schema(request=RequirementsInput, tags=["memberships"])
    def patch(self, request, case_id):
        data = RequirementsInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            item = assistance.update_requirements(request.user, case_id, data.validated_data["requirements"])
        except assistance.AssistanceError as error:
            return assistance_error(error)
        return private(Response({"requirements": item.member_note}))


class ConsultationRequestInput(serializers.Serializer):
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    address = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class MyConsultationsView(APIView):
    """POST {note, address}: ask for an at-home consultation (Royal). The address is never returned."""

    permission_classes = [IsMember]

    @extend_schema(request=ConsultationRequestInput, tags=["memberships"])
    def post(self, request, case_id):
        data = ConsultationRequestInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            item = assistance.member_case(request.user, case_id)
            consultation = assistance.request_consultation(
                item, request.user, data.validated_data["note"], data.validated_data["address"]
            )
        except assistance.AssistanceError as error:
            return assistance_error(error)
        return private(Response(assistance.consultation_data(consultation), status=status.HTTP_201_CREATED))


class ConsultationActionInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=["confirm", "cancel"])


class MyConsultationView(APIView):
    """POST {action}: confirm the proposed time (only then is it scheduled) or cancel."""

    permission_classes = [IsMember]

    @extend_schema(request=ConsultationActionInput, tags=["memberships"])
    def post(self, request, case_id, consultation_id):
        data = ConsultationActionInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            consultation = assistance.member_consultation(request.user, case_id, consultation_id, data.validated_data["action"])
        except assistance.AssistanceError as error:
            return assistance_error(error)
        return private(Response(assistance.consultation_data(consultation)))


class FamilyContactInput(serializers.Serializer):
    name = serializers.CharField(max_length=80)
    relationship = serializers.CharField(max_length=40)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    purpose = serializers.CharField(max_length=300)
    # The member's explicit permission; nothing is recorded without it.
    permission = serializers.BooleanField()

    def validate_permission(self, value):
        if value is not True:
            raise serializers.ValidationError("Tick the box to give your permission.")
        return value


class MyFamilyView(APIView):
    """POST: the member permits their matchmaker to coordinate with a named family member, for a stated purpose."""

    permission_classes = [IsMember]

    @extend_schema(request=FamilyContactInput, tags=["memberships"])
    def post(self, request, case_id):
        data = FamilyContactInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = {key: data.validated_data[key] for key in ("name", "relationship", "phone_number", "purpose")}
        try:
            item = assistance.member_case(request.user, case_id)
            contact = assistance.add_family_contact(item, request.user, **values)
        except assistance.AssistanceError as error:
            return assistance_error(error)
        return private(Response(assistance.family_data(contact), status=status.HTTP_201_CREATED))


class FamilyDecisionInput(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["grant", "withdraw"])


class MyFamilyContactView(APIView):
    """POST {decision}: grant (e.g. a contact suggested by staff) or withdraw permission."""

    permission_classes = [IsMember]

    @extend_schema(request=FamilyDecisionInput, tags=["memberships"])
    def post(self, request, case_id, contact_id):
        data = FamilyDecisionInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            contact = assistance.decide_family(request.user, case_id, contact_id, data.validated_data["decision"])
        except assistance.AssistanceError as error:
            return assistance_error(error)
        return private(Response(assistance.family_data(contact)))
