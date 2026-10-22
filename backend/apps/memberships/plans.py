"""
Membership plans the backend knows about.

The ids, names and validity match the packages on the website's /our-packages
page (frontend/features/packages/packages.ts), which remains the source of the
package copy and displayed prices. Prices are deliberately not repeated here:
there is no online payment yet, and when there is, the amount charged must be
defined and verified on the server (see apps/payments), never taken from the
browser.
"""
from dataclasses import dataclass

from django.db import models


class PlanCode(models.TextChoices):
    DIAMOND = "diamond", "Diamond Membership"
    PLATINUM = "platinum", "Platinum – Assisted Matchmaking"
    ROYAL = "royal", "Royal – Exclusive At-Home Matchmaking"


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    validity_months: int
    # Member contact numbers that may be viewed during the membership; None = not part of the plan.
    contact_view_limit: int | None


PLANS = {
    PlanCode.DIAMOND: Plan(PlanCode.DIAMOND, PlanCode.DIAMOND.label, validity_months=12, contact_view_limit=100),
    PlanCode.PLATINUM: Plan(PlanCode.PLATINUM, PlanCode.PLATINUM.label, validity_months=3, contact_view_limit=None),
    PlanCode.ROYAL: Plan(PlanCode.ROYAL, PlanCode.ROYAL.label, validity_months=12, contact_view_limit=None),
}
