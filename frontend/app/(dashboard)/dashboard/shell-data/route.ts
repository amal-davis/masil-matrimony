import { getDashboardSummary } from "@/features/dashboard/server-api";
import type { ShellData } from "@/features/dashboard/types";

/**
 * GET /dashboard/shell-data: the few live values the dashboard frame shows on
 * every page (avatar, name, badges), so the frame itself can render instantly.
 * Counts come from the API's summary; nothing is invented. Guarded by proxy.ts.
 */
export async function GET() {
  const summary = await getDashboardSummary();
  const data: ShellData = {
    name: summary.profile?.display_name || summary.member.first_name || "Member",
    profileCode: summary.profile?.profile_code ?? null,
    photoUrl: summary.profile?.photo?.url ?? null,
    membership: summary.membership?.plan_name ?? null,
    unreadNotifications: summary.notifications.unread,
    awaitingReply: summary.interests?.awaiting_your_response ?? 0,
  };
  return Response.json(data, { headers: { "Cache-Control": "private, no-store" } });
}
