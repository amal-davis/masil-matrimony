import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { MemberSummary } from "@/features/dashboard/components/member-summary";
import { MessageComposer } from "@/features/dashboard/components/message-composer";
import { Card, EmptyState, Notice, PageHeader, pageParam, secondaryButton } from "@/features/dashboard/components/ui";
import { STATIC_EXPORT } from "@/features/dashboard/preview-flag";
import { getConversation } from "@/features/dashboard/server-api";
import { profilePath } from "@/features/profiles/paths";

export const metadata: Metadata = { title: "Conversation" };

const timeFormat = new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" });

/**
 * One conversation, from the API. The API only ever returns the signed-in
 * member's own conversation with this member, and says whether they may write.
 */
export default async function ConversationPage({ params, searchParams }: PageProps<"/dashboard/messages/[code]">) {
  const { code } = await params;
  const page = STATIC_EXPORT ? 1 : pageParam((await searchParams).page);
  const data = await getConversation(code, page);
  if (!data) notFound();

  const { profile, messaging } = data;
  // The API sends newest first; read top to bottom, oldest first.
  const messages = [...data.results].reverse();
  const older = data.next ? `/dashboard/messages/${profile.profile_code}?page=${page + 1}` : null;

  return (
    <>
      <PageHeader
        title={`Messages with ${profile.display_name}`}
        actions={
          <Link href="/dashboard/messages" className={secondaryButton}>
            All messages
          </Link>
        }
      />
      <div className="flex flex-col gap-6">
        <div className="rounded-xl border border-line bg-white p-4 sm:p-5">
          <MemberSummary member={profile} />
        </div>

        <Card title="Conversation" titleId="conversation-title">
          {older && (
            <p className="mb-4 text-center">
              <Link href={older} className="text-sm font-medium text-wine-600 underline underline-offset-4">
                Show older messages
              </Link>
            </p>
          )}
          {messages.length === 0 ? (
            <EmptyState title="No messages yet">
              {messaging.can_send ? "Say hello and introduce yourself." : "Messages you exchange will appear here."}
            </EmptyState>
          ) : (
            <ol className="flex flex-col gap-3" aria-label="Messages, oldest first">
              {messages.map((message) => (
                <li key={message.id} className={message.mine ? "flex justify-end" : "flex justify-start"}>
                  <div
                    className={
                      message.mine
                        ? "max-w-[85%] rounded-2xl rounded-br-sm bg-wine-600 px-4 py-2.5 text-white sm:max-w-[70%]"
                        : "max-w-[85%] rounded-2xl rounded-bl-sm bg-mist px-4 py-2.5 text-ink sm:max-w-[70%]"
                    }
                  >
                    <p className="sr-only">{message.mine ? "You wrote:" : `${profile.display_name} wrote:`}</p>
                    <p className="text-[0.9375rem] break-words whitespace-pre-line">{message.body}</p>
                    <p className={message.mine ? "mt-1 text-xs text-white/75" : "mt-1 text-xs text-ink-muted"}>
                      {timeFormat.format(new Date(message.sent_at))}
                      {message.mine && message.read_at ? " · Read" : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          )}

          <div className="mt-6 border-t border-line pt-5">
            {messaging.can_send ? (
              <MessageComposer profileCode={profile.profile_code} name={profile.display_name} />
            ) : (
              <Notice role="status">
                {messaging.message}{" "}
                {messaging.code === "upgrade_required" && (
                  <Link href="/dashboard/membership" className="font-medium text-wine-600 underline underline-offset-4">
                    See membership plans
                  </Link>
                )}
                {messaging.code === "interest_required" && profile.available && (
                  <Link href={profilePath(profile.profile_code)} className="font-medium text-wine-600 underline underline-offset-4">
                    View profile
                  </Link>
                )}
              </Notice>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}
