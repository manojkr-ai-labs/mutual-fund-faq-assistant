import {
  DEFAULT_HINT,
  DISCLAIMER,
  FALLBACK_AS_OF,
  FALLBACK_CITATION_LABEL,
  FALLBACK_CITATION_URL,
  PROCESS_HINT,
} from "./constants";
import type { AskResponse } from "./types";

const UNAVAILABLE: AskResponse = {
  type: "error",
  text: "The assistant is temporarily unavailable. Try again in a moment. Published facts remain on groww.in.",
  citation_url: FALLBACK_CITATION_URL,
  citation_label: FALLBACK_CITATION_LABEL,
  last_updated_from_sources: FALLBACK_AS_OF,
  disclaimer: DISCLAIMER,
};

function isAskResponse(value: unknown): value is AskResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const record = value as Record<string, unknown>;
  return (
    typeof record.type === "string" &&
    typeof record.text === "string" &&
    typeof record.citation_url === "string" &&
    typeof record.citation_label === "string" &&
    typeof record.last_updated_from_sources === "string" &&
    typeof record.disclaimer === "string"
  );
}

export async function askQuestion(question: string): Promise<AskResponse> {
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const payload: unknown = await response.json();
    if (isAskResponse(payload)) {
      return payload;
    }
    return UNAVAILABLE;
  } catch {
    return UNAVAILABLE;
  }
}

export function loadingHint(question: string): string {
  return /download|capital gain|statement|report|transaction history/i.test(
    question,
  )
    ? PROCESS_HINT
    : DEFAULT_HINT;
}

export function isProcessCitation(url: string): boolean {
  return url.includes("groww.in/help/");
}
