"use client";

import Link from "next/link";
import { useState, useTransition } from "react";

import { markAllNotificationsRead, markNotificationRead } from "../actions";
import { quietButton, secondaryButton } from "./ui";

export function MarkAllRead() {
  const [busy, start] = useTransition();
  const [error, setError] = useState("");
  return (
    <div>
      <button
        type="button"
        disabled={busy}
        onClick={() => start(async () => {
          const result = await markAllNotificationsRead();
          setError(result.ok ? "" : result.message);
        })}
        className={secondaryButton}
      >
        {busy ? "Saving…" : "Mark all as read"}
      </button>
      <p role="alert" className="mt-1 text-sm text-danger empty:hidden">{error}</p>
    </div>
  );
}

/** "Open" marks the notification read on the server, then follows its link. */
export function NotificationLink({ id, href, read }: { id: string; href: string; read: boolean }) {
  const [busy, start] = useTransition();
  if (read) {
    return href ? <Link href={href} className={quietButton}>Open</Link> : null;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {href && (
        <Link href={href} onClick={() => void markNotificationRead(id)} className={quietButton}>
          Open
        </Link>
      )}
      <button type="button" disabled={busy} onClick={() => start(async () => void (await markNotificationRead(id)))} className={quietButton}>
        Mark as read
      </button>
    </div>
  );
}
