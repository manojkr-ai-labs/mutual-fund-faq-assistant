import { DISCLAIMER } from "@/lib/constants";
import {
  FALLBACK_AS_OF,
  FALLBACK_CITATION_LABEL,
  FALLBACK_CITATION_URL,
} from "@/lib/constants";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

const ASK_API_ORIGIN = (
  process.env.ASK_API_ORIGIN ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const UNAVAILABLE = {
  type: "error",
  text: "The assistant is temporarily unavailable. Try again in a moment. Published facts remain on groww.in.",
  citation_url: FALLBACK_CITATION_URL,
  citation_label: FALLBACK_CITATION_LABEL,
  last_updated_from_sources: FALLBACK_AS_OF,
  disclaimer: DISCLAIMER,
};

export async function POST(request: Request) {
  let question = "";
  try {
    const body: unknown = await request.json();
    if (
      typeof body === "object" &&
      body !== null &&
      "question" in body &&
      typeof body.question === "string"
    ) {
      question = body.question;
    }
  } catch {
    return Response.json(UNAVAILABLE, { status: 502 });
  }

  try {
    const upstream = await fetch(`${ASK_API_ORIGIN}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data: unknown = await upstream.json();
    return Response.json(data, { status: upstream.status });
  } catch {
    return Response.json(UNAVAILABLE, { status: 502 });
  }
}
