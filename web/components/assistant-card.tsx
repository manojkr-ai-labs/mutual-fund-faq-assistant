import { isProcessCitation } from "@/lib/ask";
import type { AskResponse } from "@/lib/types";

type CardLook = {
  badge: string;
  rail: string;
  wash: string;
  badgeClass: string;
};

function appearance(response: AskResponse): CardLook {
  if (response.type === "refuse") {
    return {
      badge: "Refused · not advice",
      rail: "border-l-amber-rail",
      wash: "bg-amber-wash",
      badgeClass: "bg-amber-rail text-white",
    };
  }
  if (response.type === "factsheet_only") {
    return {
      badge: "Scheme page only",
      rail: "border-l-info-rail",
      wash: "bg-info-wash",
      badgeClass: "bg-info-rail text-white",
    };
  }
  if (response.type === "error") {
    return {
      badge: "Unavailable",
      rail: "border-l-muted",
      wash: "bg-paper",
      badgeClass: "bg-muted text-white",
    };
  }
  if (isProcessCitation(response.citation_url)) {
    return {
      badge: "Process",
      rail: "border-l-mint",
      wash: "bg-paper",
      badgeClass: "bg-mint text-white",
    };
  }
  return {
    badge: "Answer",
    rail: "border-l-mint",
    wash: "bg-paper",
    badgeClass: "bg-mint text-white",
  };
}

export function AssistantCard({ response }: { response: AskResponse }) {
  const look = appearance(response);

  return (
    <article
      className={`rounded-card border border-hairline border-l-4 ${look.rail} ${look.wash} p-4`}
    >
      <p
        className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ${look.badgeClass}`}
      >
        {look.badge}
      </p>
      <p className="mt-3 text-[15px] leading-6 text-ink">{response.text}</p>
      <a
        href={response.citation_url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-3 inline-block text-sm font-medium text-mint underline underline-offset-4"
      >
        {response.citation_label}
      </a>
      <p className="mt-2 text-[13px] leading-5 text-muted">
        Last updated from sources: {response.last_updated_from_sources}
      </p>
      {response.type === "refuse" ? (
        <p className="mt-3 text-xs text-muted">
          You can still ask a scheme fact, such as expense ratio or exit load.
        </p>
      ) : null}
    </article>
  );
}
