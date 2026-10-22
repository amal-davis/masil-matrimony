import Link from "next/link";

import { UserIcon } from "@/components/ui/icons";

import { EmptyState, primaryButton } from "./ui";

/** Shown on pages that need a profile when the member hasn't created one. */
export function NoProfile({ children }: { children: string }) {
  return (
    <EmptyState
      icon={<UserIcon className="size-6" />}
      title="Create your profile first"
      action={
        <Link href="/dashboard/my-profile" className={primaryButton}>
          Create my profile
        </Link>
      }
    >
      {children}
    </EmptyState>
  );
}
