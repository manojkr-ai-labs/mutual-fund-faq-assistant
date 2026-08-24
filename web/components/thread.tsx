import type { Turn } from "@/lib/types";

import { AssistantCard } from "./assistant-card";

export function Thread({ turns }: { turns: Turn[] }) {
  return (
    <div className="flex flex-col gap-8 py-6">
      {turns.map((turn) => {
        if (turn.role === "user") {
          return (
            <p
              key={turn.id}
              className="ml-auto max-w-[85%] rounded-card bg-mint-soft px-4 py-3 text-sm leading-[22px] text-ink"
            >
              {turn.text}
            </p>
          );
        }
        if (turn.role === "pending") {
          return (
            <div
              key={turn.id}
              className="flex items-center gap-3 text-sm text-muted"
              aria-live="polite"
            >
              <span className="flex gap-1" aria-hidden="true">
                <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-mint" />
                <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-mint" />
                <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-mint" />
              </span>
              {turn.hint}
            </div>
          );
        }
        return <AssistantCard key={turn.id} response={turn.response} />;
      })}
    </div>
  );
}
