import { DISCLAIMER } from "@/lib/constants";

import { Mark } from "./mark";

export function TopBar() {
  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-canvas/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[720px] items-center justify-between gap-3 px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Mark className="h-8 w-8 shrink-0" />
          <p className="truncate font-display text-lg font-medium tracking-tight text-ink sm:text-xl">
            Mutual Fund FAQ Assistant
          </p>
        </div>
        <p className="hidden shrink-0 rounded-full bg-mint px-3 py-1.5 text-xs font-semibold tracking-wide text-white md:block">
          {DISCLAIMER}
        </p>
      </div>
      <p className="bg-mint px-6 py-2 text-center text-xs font-semibold tracking-wide text-white md:hidden">
        {DISCLAIMER}
      </p>
    </header>
  );
}
