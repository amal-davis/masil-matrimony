import { formatDate } from "../format";
import type { ContactExchangeItem, ExchangeStatus } from "../types";
import { ConsentControls } from "./consent-controls";
import { MemberSummary } from "./member-summary";
import { Badge, type BadgeTone } from "./ui";

const TONE: Record<ExchangeStatus, BadgeTone> = {
  pending: "info",
  shared: "success",
  declined: "neutral",
  cancelled: "neutral",
};

/** One matchmaker-proposed exchange of mobile numbers, with what the member is asked to agree to. */
export function ContactExchangeCard({ exchange }: { exchange: ContactExchangeItem }) {
  return (
    <article className="rounded-xl border border-line bg-white p-4 sm:p-5">
      <MemberSummary member={{ ...exchange.profile, available: true }}>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Badge tone={TONE[exchange.status]}>{exchange.status_label}</Badge>
          <span className="text-sm text-ink-muted">Proposed {formatDate(exchange.created_at)}</span>
        </div>
      </MemberSummary>
      <p className="mt-4 text-[0.9375rem]">
        <span className="font-medium">Purpose:</span> {exchange.purpose}
      </p>
      <p className="mt-2 rounded-lg bg-mist px-3 py-2 text-sm text-ink">{exchange.statement}</p>
      {exchange.phone_number ? (
        <p className="mt-3 text-[0.9375rem]">
          <span className="font-medium">{exchange.profile.display_name}&apos;s mobile number:</span>{" "}
          <a href={`tel:${exchange.phone_number}`} className="font-semibold text-wine-600 tabular-nums underline underline-offset-4">
            {exchange.phone_number}
          </a>
        </p>
      ) : exchange.status === "declined" || exchange.status === "cancelled" ? (
        <p className="mt-3 text-sm text-ink-muted">This exchange didn&apos;t go ahead. No numbers were shared.</p>
      ) : (
        <p className="mt-3 text-sm text-ink-muted">Numbers stay hidden until both of you consent.</p>
      )}
      <ConsentControls exchange={exchange} />
    </article>
  );
}
