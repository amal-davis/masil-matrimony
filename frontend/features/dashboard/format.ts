import type { BadgeTone } from "./components/ui";
import type { InterestStatus, MemberCard, PhotoStatus, ProfileStatus, Subscription } from "./types";

const dateFormat = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });

/** "22 Oct 2026". Rendered on the server only, so there's no hydration mismatch. */
export const formatDate = (iso: string | null | undefined) => (iso ? dateFormat.format(new Date(iso)) : "—");

export function formatMemberLocation({ city, district, state }: MemberCard["location"]) {
  return [city || district, state].filter(Boolean).join(", ");
}

export const profileStatus: Record<ProfileStatus, { label: string; tone: BadgeTone }> = {
  draft: { label: "Not yet submitted", tone: "neutral" },
  pending_review: { label: "Under review", tone: "info" },
  active: { label: "Approved", tone: "success" },
  rejected: { label: "Changes requested", tone: "danger" },
  suspended: { label: "Suspended", tone: "danger" },
};

export const photoStatus: Record<PhotoStatus, { label: string; tone: BadgeTone }> = {
  pending: { label: "Pending review", tone: "info" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Not approved", tone: "danger" },
};

export const interestStatus: Record<InterestStatus, { label: string; tone: BadgeTone }> = {
  pending: { label: "Awaiting response", tone: "info" },
  accepted: { label: "Accepted", tone: "success" },
  declined: { label: "Declined", tone: "neutral" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
};

/** Interest status worded from the member's side: a pending received interest awaits *their* reply. */
export function interestStatusFor(status: InterestStatus, direction: "sent" | "received" | undefined) {
  return status === "pending" && direction === "received"
    ? { label: "Awaiting your reply", tone: "brand" as BadgeTone }
    : interestStatus[status];
}

export const subscriptionStatus: Record<Subscription["status"], { label: string; tone: BadgeTone }> = {
  pending: { label: "Pending activation", tone: "info" },
  active: { label: "Active", tone: "success" },
  upcoming: { label: "Starts soon", tone: "info" },
  expired: { label: "Expired", tone: "neutral" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};
