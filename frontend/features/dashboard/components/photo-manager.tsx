"use client";

import { useRouter } from "next/navigation";
import { useId, useRef, useState, useTransition, type DragEvent } from "react";

import { cn } from "@/lib/utils";

import { deletePhoto, setPrimaryPhoto } from "../actions";
import { photoStatus } from "../format";
import type { OwnPhoto } from "../types";
import { ConfirmDialog } from "./confirm-dialog";
import { ImageIcon, StarIcon, TrashIcon, UploadIcon } from "./icons";
import { Badge, Notice, quietButton } from "./ui";

/** Browser-side checks for a quick answer; the API decodes the file and has the final say. */
const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 8 * 1024 * 1024;

type Upload = { name: string; progress: number } | null;
type Message = { tone: "success" | "danger"; text: string } | null;

function uploadPhoto(file: File, onProgress: (percent: number) => void): Promise<{ status: number; body: Record<string, unknown> }> {
  // XMLHttpRequest rather than fetch: it reports upload progress.
  return new Promise((resolve) => {
    const request = new XMLHttpRequest();
    request.open("POST", "/dashboard/photos/upload");
    request.responseType = "json";
    request.upload.onprogress = (event) => event.lengthComputable && onProgress(Math.round((event.loaded / event.total) * 100));
    request.onload = () => resolve({ status: request.status, body: (request.response as Record<string, unknown>) ?? {} });
    request.onerror = () => resolve({ status: 0, body: {} });
    const form = new FormData();
    form.append("photo", file);
    request.send(form);
  });
}

function uploadError(status: number, body: Record<string, unknown>): string {
  // DRF sends a field error as a list, or as a plain string when raised as one.
  const field = Array.isArray(body.photo) ? body.photo[0] : body.photo;
  if (typeof field === "string") return field;
  if (typeof body.detail === "string") return body.detail;
  if (status === 0) return "The upload didn't reach our server. Please check your connection and try again.";
  if (status === 413) return "The photo is too large.";
  return "The photo couldn't be uploaded. Please try again.";
}

function PhotoImage({ photo, alt, className }: { photo: OwnPhoto; alt: string; className?: string }) {
  return (
    // Signed, short-lived URL: plain <img>, nothing for the optimiser to cache.
    // eslint-disable-next-line @next/next/no-img-element
    <img src={photo.url} alt={alt} width={photo.width} height={photo.height} className={cn("absolute inset-0 size-full object-cover object-[50%_25%]", className)} />
  );
}

export function PhotoManager({ photos, maxPhotos }: { photos: OwnPhoto[]; maxPhotos: number }) {
  const id = useId();
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [upload, setUpload] = useState<Upload>(null);
  const [dragging, setDragging] = useState(false);
  const [message, setMessage] = useState<Message>(null);
  const [removing, setRemoving] = useState<OwnPhoto | null>(null);
  const [busy, startBusy] = useTransition();

  const primary = photos.find((photo) => photo.is_primary) ?? null;
  const others = photos.filter((photo) => photo !== primary);
  const usable = photos.filter((photo) => photo.status !== "rejected").length;
  const full = usable >= maxPhotos;
  const uploadDisabled = Boolean(upload) || full;

  const onFile = async (file: File | undefined) => {
    if (inputRef.current) inputRef.current.value = "";
    if (!file || uploadDisabled) return;
    setMessage(null);
    if (!ACCEPTED_TYPES.includes(file.type)) return setMessage({ tone: "danger", text: "Choose a JPEG, PNG or WebP photo." });
    if (file.size > MAX_BYTES) return setMessage({ tone: "danger", text: "The photo is larger than 8 MB. Please choose a smaller file." });

    setUpload({ name: file.name, progress: 0 });
    const { status, body } = await uploadPhoto(file, (progress) => setUpload({ name: file.name, progress }));
    setUpload(null);
    if (status === 401) {
      router.push(`/login?next=${encodeURIComponent("/dashboard/photos")}`);
      return;
    }
    if (status !== 201) return setMessage({ tone: "danger", text: uploadError(status, body) });
    setMessage({ tone: "success", text: "Photo uploaded. Other members will see it once our team approves it." });
    router.refresh();
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    void onFile(event.dataTransfer.files?.[0]);
  };

  const act = (action: () => Promise<{ ok: boolean; message?: string }>, success: string) =>
    startBusy(async () => {
      const result = await action();
      setRemoving(null);
      setMessage(result.ok ? { tone: "success", text: success } : { tone: "danger", text: result.message ?? "Please try again." });
    });

  return (
    <div className="flex flex-col gap-6">
      <div aria-live="polite" className="empty:hidden">
        {message && (
          <Notice tone={message.tone} role={message.tone === "danger" ? "alert" : "status"}>
            {message.text}
          </Notice>
        )}
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
        {/* Main photo */}
        <section aria-labelledby={`${id}-primary`} className="overflow-hidden rounded-xl border border-line bg-white">
          <div className="border-b border-line px-5 py-4">
            <h2 id={`${id}-primary`} className="text-base font-semibold">
              Main photo
            </h2>
            <p className="mt-0.5 text-sm text-ink-muted">Shown on your profile card and in matches.</p>
          </div>
          <div className="p-4">
            <div className="relative mx-auto aspect-[4/5] w-full max-w-72 overflow-hidden rounded-lg bg-mist lg:max-w-none">
              {primary ? (
                <>
                  <PhotoImage photo={primary} alt="Your main photo" />
                  <div className="absolute top-2 left-2 rounded-full bg-white shadow-sm">
                    <Badge tone={photoStatus[primary.status].tone}>{photoStatus[primary.status].label}</Badge>
                  </div>
                </>
              ) : (
                <div className="flex size-full flex-col items-center justify-center gap-2 p-6 text-center text-ink-muted">
                  <ImageIcon className="size-10" />
                  <p className="text-sm">No main photo yet. Your first upload becomes your main photo.</p>
                </div>
              )}
            </div>
            {primary && (
              <div className="mt-3 flex justify-center">
                <button type="button" disabled={busy} onClick={() => setRemoving(primary)} className={cn(quietButton, "text-danger hover:bg-danger/5")}>
                  <TrashIcon className="size-4.5" />
                  Remove main photo
                </button>
              </div>
            )}
            {primary?.status === "rejected" && primary.review_note && (
              <p className="mt-2 text-sm text-danger">{primary.review_note}</p>
            )}
          </div>
        </section>

        <div className="flex min-w-0 flex-col gap-6">
          {/* Upload area */}
          <section aria-labelledby={`${id}-upload`}>
            <h2 id={`${id}-upload`} className="sr-only">
              Upload a photo
            </h2>
            <input
              ref={inputRef}
              id={`${id}-file`}
              type="file"
              accept={ACCEPTED_TYPES.join(",")}
              // Visually hidden but focusable; the label below shows its focus ring.
              className="peer sr-only"
              disabled={uploadDisabled}
              onChange={(event) => onFile(event.target.files?.[0])}
            />
            <label
              htmlFor={`${id}-file`}
              onDragOver={(event) => {
                event.preventDefault();
                if (!uploadDisabled) setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={cn(
                "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed bg-white px-6 py-10 text-center transition-colors",
                "peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-wine-600",
                dragging ? "border-wine-600 bg-brand-50" : "border-field-line/50 hover:border-wine-600/60 hover:bg-mist/50",
                uploadDisabled && "pointer-events-none opacity-70",
              )}
            >
              <span aria-hidden="true" className="flex size-12 items-center justify-center rounded-full bg-brand-50 text-wine-600">
                <UploadIcon className="size-6" />
              </span>
              {upload ? (
                <span className="w-full max-w-sm" role="status">
                  <span className="block truncate text-[0.9375rem] font-medium text-ink">Uploading {upload.name}…</span>
                  <span
                    role="progressbar"
                    aria-label="Upload progress"
                    aria-valuenow={upload.progress}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    className="mt-3 block h-2 overflow-hidden rounded-full bg-surface-muted"
                  >
                    <span className="block h-full bg-wine-600 transition-[width] motion-reduce:transition-none" style={{ width: `${upload.progress}%` }} />
                  </span>
                </span>
              ) : full ? (
                <span className="text-[0.9375rem] text-ink">
                  You&apos;ve reached the limit of {maxPhotos} photos. Remove one to add another.
                </span>
              ) : (
                <>
                  <span className="text-[0.9375rem] text-ink">
                    <span className="font-semibold text-wine-600">Choose a photo</span>
                    <span className="hidden sm:inline"> or drag it here</span>
                  </span>
                  <span className="text-sm text-ink-muted">
                    JPEG, PNG or WebP, up to 8 MB · {usable} of {maxPhotos} used
                  </span>
                </>
              )}
            </label>
            <ul className="mt-3 grid gap-1.5 text-sm text-ink-muted sm:grid-cols-3">
              <li>· A clear, recent photo of your face</li>
              <li>· Good light, no sunglasses</li>
              <li>· Reviewed by our team before it&apos;s shown</li>
            </ul>
          </section>

          {/* Other photos */}
          <section aria-labelledby={`${id}-others`} className="rounded-xl border border-line bg-white">
            <div className="border-b border-line px-5 py-4">
              <h2 id={`${id}-others`} className="text-base font-semibold">
                More photos
              </h2>
              <p className="mt-0.5 text-sm text-ink-muted">Help families see more of you. Any approved photo can become your main photo.</p>
            </div>
            {others.length === 0 ? (
              <p className="px-5 py-8 text-center text-[0.9375rem] text-ink-muted">No other photos yet.</p>
            ) : (
              <ul className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 xl:grid-cols-4">
                {others.map((photo, index) => (
                  <li key={photo.id} className="flex flex-col overflow-hidden rounded-lg border border-line">
                    <div className="relative aspect-[4/5] bg-mist">
                      <PhotoImage photo={photo} alt={`Your photo ${index + 2}`} />
                      <div className="absolute top-1.5 left-1.5 rounded-full bg-white shadow-sm">
                        <Badge tone={photoStatus[photo.status].tone}>{photoStatus[photo.status].label}</Badge>
                      </div>
                    </div>
                    {photo.status === "rejected" && photo.review_note && (
                      <p className="border-t border-line px-2.5 py-1.5 text-xs text-danger">{photo.review_note}</p>
                    )}
                    <div className="flex flex-col border-t border-line">
                      {photo.status !== "rejected" && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => act(() => setPrimaryPhoto(photo.id), "Main photo updated.")}
                          className="inline-flex min-h-11 items-center justify-center gap-1.5 text-sm font-medium text-wine-600 hover:bg-brand-50 focus-visible:outline-wine-600 disabled:opacity-60"
                        >
                          <StarIcon className="size-4" />
                          Make main photo
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => setRemoving(photo)}
                        aria-label={`Remove photo ${index + 2}`}
                        className="inline-flex min-h-11 items-center justify-center gap-1.5 border-t border-line text-sm font-medium text-ink-muted hover:bg-danger/5 hover:text-danger focus-visible:outline-wine-600 disabled:opacity-60"
                      >
                        <TrashIcon className="size-4" />
                        Remove
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>

      <ConfirmDialog
        open={removing !== null}
        busy={busy}
        tone="danger"
        title="Remove this photo?"
        confirmLabel="Remove photo"
        onConfirm={() => removing && act(() => deletePhoto(removing.id), "Photo removed.")}
        onCancel={() => setRemoving(null)}
      >
        {removing?.is_primary
          ? "This is your main photo. Your next photo will become the main photo. This can't be undone."
          : "The photo will be deleted. This can't be undone."}
      </ConfirmDialog>
    </div>
  );
}
