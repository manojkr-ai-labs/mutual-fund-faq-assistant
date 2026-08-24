export function Mark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <rect x="5.5" y="4.5" width="16" height="22" rx="2.2" fill="#ffffff" stroke="#D7E2DC" />
      <path d="M17.5 4.5V12h8" fill="#E6F6EF" stroke="#D7E2DC" />
      <path d="M17.5 4.5 25.5 12" stroke="#D7E2DC" />
      <circle cx="22.5" cy="22.5" r="6.5" fill="#0E9F6E" />
      <path
        d="M19.6 22.6 21.7 24.6 25.4 20.4"
        fill="none"
        stroke="#ffffff"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
