import {
  EXAMPLE_QUESTIONS,
  SCHEME_TAGS,
  WELCOME_BODY,
  WELCOME_HEADLINE,
} from "@/lib/constants";

type WelcomeProps = {
  disabled?: boolean;
  onExample: (question: string) => void;
};

export function Welcome({ disabled = false, onExample }: WelcomeProps) {
  return (
    <section className="flex flex-1 flex-col justify-center py-6 sm:py-10">
      <h1 className="max-w-xl font-display text-[32px] font-semibold leading-10 tracking-tight text-ink sm:text-[40px] sm:leading-12">
        {WELCOME_HEADLINE}
      </h1>
      <p className="mt-4 max-w-2xl text-base leading-[26px] text-muted">{WELCOME_BODY}</p>
      <ul className="mt-8 flex flex-wrap gap-2">
        {SCHEME_TAGS.map((tag) => (
          <li
            key={tag}
            className="rounded-full border border-hairline bg-paper px-3 py-1 text-xs font-semibold tracking-wide text-muted"
          >
            {tag}
          </li>
        ))}
      </ul>
      <p className="mt-10 text-xs font-semibold tracking-[0.12em] text-muted uppercase">
        Try an example
      </p>
      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
        {EXAMPLE_QUESTIONS.map((question) => (
          <button
            key={question}
            type="button"
            disabled={disabled}
            onClick={() => onExample(question)}
            className="rounded-card border border-hairline border-l-4 border-l-mint bg-paper p-4 text-left text-sm leading-[22px] text-ink transition hover:bg-mint-soft disabled:cursor-not-allowed disabled:opacity-60"
          >
            {question}
          </button>
        ))}
      </div>
    </section>
  );
}
