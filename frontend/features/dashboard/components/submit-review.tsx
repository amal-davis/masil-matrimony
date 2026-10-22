"use client";

import { useState, useTransition } from "react";

import { submitProfileForReview } from "../actions";
import { ConfirmDialog } from "./confirm-dialog";
import { Notice, primaryButton } from "./ui";

/** Sends a complete profile to staff. The API re-checks completeness and status. */
export function SubmitReview({ resubmit }: { resubmit: boolean }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const [busy, start] = useTransition();

  const confirm = () =>
    start(async () => {
      const result = await submitProfileForReview();
      setOpen(false);
      if (!result.ok) setError(result.message);
    });

  return (
    <div>
      <button type="button" onClick={() => setOpen(true)} className={primaryButton}>
        {resubmit ? "Resubmit for review" : "Submit for review"}
      </button>
      <div role="alert" className="mt-3 empty:hidden">
        {error && <Notice tone="danger">{error}</Notice>}
      </div>
      <ConfirmDialog
        open={open}
        busy={busy}
        title="Submit your profile for review?"
        confirmLabel="Submit"
        onConfirm={confirm}
        onCancel={() => setOpen(false)}
      >
        Our team will check your profile before other members can see it. After you submit, your name, gender and date
        of birth can only be changed by contacting us.
      </ConfirmDialog>
    </div>
  );
}
