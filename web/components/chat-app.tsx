"use client";

import { useRef, useState } from "react";

import { askQuestion, loadingHint } from "@/lib/ask";
import type { Turn } from "@/lib/types";

import { Composer } from "./composer";
import { Thread } from "./thread";
import { TopBar } from "./top-bar";
import { Welcome } from "./welcome";

function newId(): string {
  return crypto.randomUUID();
}

export function ChatApp() {
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [pending, setPending] = useState(false);
  const scrollerRef = useRef<HTMLDivElement>(null);

  async function submit(question: string) {
    const trimmed = question.trim();
    if (!trimmed || pending) {
      return;
    }

    const userId = newId();
    const pendingId = newId();
    setDraft("");
    setPending(true);
    setTurns((current) => [
      ...current,
      { id: userId, role: "user", text: trimmed },
      { id: pendingId, role: "pending", hint: loadingHint(trimmed) },
    ]);
    requestAnimationFrame(() => {
      scrollerRef.current?.scrollTo({
        top: scrollerRef.current.scrollHeight,
        behavior: "smooth",
      });
    });

    const response = await askQuestion(trimmed);
    setTurns((current) =>
      current.map((turn) =>
        turn.id === pendingId
          ? { id: pendingId, role: "assistant", response }
          : turn,
      ),
    );
    setPending(false);
    requestAnimationFrame(() => {
      scrollerRef.current?.scrollTo({
        top: scrollerRef.current.scrollHeight,
        behavior: "smooth",
      });
    });
  }

  const empty = turns.length === 0;

  return (
    <div className="flex h-dvh flex-col bg-canvas">
      <TopBar />
      <div ref={scrollerRef} className="flex-1 overflow-y-auto">
        <main className="mx-auto flex min-h-full max-w-[720px] flex-col px-6 pb-8">
          {empty ? (
            <Welcome disabled={pending} onExample={(question) => void submit(question)} />
          ) : (
            <Thread turns={turns} />
          )}
        </main>
      </div>
      <Composer
        value={draft}
        pending={pending}
        onChange={setDraft}
        onSubmit={() => void submit(draft)}
      />
    </div>
  );
}
