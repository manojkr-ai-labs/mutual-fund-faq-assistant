"use client";

import { useLayoutEffect, useRef } from "react";

import { COMPOSER_HINT, SOURCES_FOOTER } from "@/lib/constants";

type ComposerProps = {
  value: string;
  pending: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function Composer({ value, pending, onChange, onSubmit }: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const canSend = value.trim().length > 0 && !pending;

  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) {
      return;
    }
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  return (
    <div className="border-t border-hairline bg-canvas px-6 pt-4 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
      <form
        className="mx-auto flex max-w-[720px] items-end gap-2 rounded-card border border-hairline bg-paper p-2 shadow-[var(--shadow-composer)]"
        onSubmit={(event) => {
          event.preventDefault();
          if (canSend) {
            onSubmit();
          }
        }}
      >
        <label htmlFor="question" className="sr-only">
          Ask a scheme fact
        </label>
        <textarea
          id="question"
          ref={textareaRef}
          rows={1}
          value={value}
          disabled={pending}
          placeholder="Ask a published scheme fact"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (canSend) {
                onSubmit();
              }
            }
          }}
          className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-sm leading-[22px] text-ink outline-none placeholder:text-muted/70 disabled:opacity-70"
        />
        <button
          type="submit"
          disabled={!canSend}
          aria-label="Send question"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-card bg-mint text-white transition enabled:hover:brightness-95 disabled:bg-hairline disabled:text-muted"
        >
          <svg viewBox="0 0 20 20" className="h-5 w-5" aria-hidden="true">
            <path
              d="M10 16V5M5.5 9.5 10 5l4.5 4.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </form>
      <p className="mx-auto mt-3 max-w-[720px] text-center text-xs leading-4 text-muted">
        {COMPOSER_HINT}
      </p>
      <p className="mx-auto mt-1 max-w-[720px] text-center text-xs text-muted/80">
        {SOURCES_FOOTER}
      </p>
    </div>
  );
}
