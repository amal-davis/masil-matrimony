"use client";

import { useId, useState, useTransition } from "react";

import { Select } from "@/components/ui/form-field";

import { updateProfile } from "../actions";
import { contactSharingOptions, photoVisibilityOptions, visibilityOptions } from "../profile-options";
import { Notice, primaryButton } from "./ui";

type Privacy = { visibility: string; photo_visibility: string; contact_sharing?: string };

/**
 * Who can see the profile, its photos and (when `initial.contact_sharing` is
 * given) the member's mobile number. Saved through the profile API.
 */
export function PrivacySettings({ initial, showProfileVisibility = true }: { initial: Privacy; showProfileVisibility?: boolean }) {
  const id = useId();
  const [values, setValues] = useState(initial);
  const [message, setMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);
  const [saving, start] = useTransition();
  const showContactSharing = initial.contact_sharing !== undefined;
  const dirty =
    values.visibility !== initial.visibility ||
    values.photo_visibility !== initial.photo_visibility ||
    values.contact_sharing !== initial.contact_sharing;

  const save = () =>
    start(async () => {
      const payload = showProfileVisibility ? values : { photo_visibility: values.photo_visibility };
      const result = await updateProfile(payload as never);
      setMessage(result.ok ? { tone: "success", text: "Privacy settings saved." } : { tone: "danger", text: result.message });
    });

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        save();
      }}
      className="flex flex-col gap-5"
    >
      {showProfileVisibility && (
        <div>
          <label htmlFor={`${id}-visibility`} className="block text-sm font-medium text-ink">
            Who can see my profile
          </label>
          <div className="mt-1.5 max-w-md">
            <Select
              id={`${id}-visibility`}
              value={values.visibility}
              onChange={(event) => setValues({ ...values, visibility: event.target.value })}
              aria-describedby={`${id}-visibility-hint`}
            >
              {visibilityOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </Select>
          </div>
          <p id={`${id}-visibility-hint`} className="mt-1.5 text-sm text-ink-muted">
            Hidden profiles don&apos;t appear in matches and can&apos;t receive new interests.
          </p>
        </div>
      )}
      <div>
        <label htmlFor={`${id}-photos`} className="block text-sm font-medium text-ink">
          Who can see my photos
        </label>
        <div className="mt-1.5 max-w-md">
          <Select
            id={`${id}-photos`}
            value={values.photo_visibility}
            onChange={(event) => setValues({ ...values, photo_visibility: event.target.value })}
          >
            {photoVisibilityOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </Select>
        </div>
      </div>
      {showContactSharing && (
        <div>
          <label htmlFor={`${id}-contact`} className="block text-sm font-medium text-ink">
            Who can see my mobile number
          </label>
          <div className="mt-1.5 max-w-md">
            <Select
              id={`${id}-contact`}
              value={values.contact_sharing}
              onChange={(event) => setValues({ ...values, contact_sharing: event.target.value })}
              aria-describedby={`${id}-contact-hint`}
            >
              {contactSharingOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </Select>
          </div>
          <p id={`${id}-contact-hint`} className="mt-1.5 max-w-prose text-sm text-ink-muted">
            Your number is never on your public profile. If you share it, members whose paid package includes
            contact access can view it, and each view counts toward their package&apos;s limit. Free members never
            see it. You can stop sharing at any time.
          </p>
        </div>
      )}
      <div aria-live="polite" className="empty:hidden">
        {message && <Notice tone={message.tone}>{message.text}</Notice>}
      </div>
      <div>
        <button type="submit" disabled={saving || !dirty} className={primaryButton}>
          {saving ? "Saving…" : "Save privacy settings"}
        </button>
      </div>
    </form>
  );
}
