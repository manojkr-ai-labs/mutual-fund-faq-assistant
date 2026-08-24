# Phase 6.2 — Google Stitch (single prompt)

Stitch settings: **Web · Desktop 1440 · latest model · light · English (India)**. Paste the block below as the entire first prompt.

```
Design a premium desktop web app (1440px) plus a matching mobile frame (390px) called “Mutual Fund FAQ Assistant”: a facts-only Q&A for five HDFC Direct Growth schemes. Groww is the UX reference (calm, mint, lots of air, question-first). This is NOT a Groww clone, not a trading terminal, and not ChatGPT-with-a-sidebar.

Visual system (use on every screen): sage canvas #F4F7F5, paper #FFFFFF, ink #12221C, muted #5C6F68, hairline #D7E2DC, accent mint #0E9F6E and mint-soft #E6F6EF. UI type Plus Jakarta Sans; welcome headline in Fraunces. 14px radii, 44px controls, 720px centered conversation column, generous whitespace, WCAG AA. Original mark: a folded factsheet with a mint check — do not use the Groww logo.

Shared chrome on every screen: (1) sticky top bar with mark + “Mutual Fund FAQ Assistant” on the left and a persistent mint pill that reads exactly “Facts-only. No investment advice.” — this pill must stay visible without scrolling; (2) sticky composer at the bottom of the column: auto-growing textarea, mint send, helper “Do not enter PAN, Aadhaar, email, phone, or folio.”; (3) tiny footer “Sources: groww.in · History stays in this tab only.” Hard bans on all screens: sign-in, profile, PAN/folio/OTP fields, file upload, return charts, comparison tables, “Invest now”, “Want a recommendation?” chips, stock photos of investors, candlesticks, a second source link.

Generate these screens in one project, identical chrome:

SCREEN 1 — Welcome / empty (desktop 1440×900). Vertically balanced hero above the composer. Serif headline “Ask a published scheme fact.” Body: “This assistant restates expense ratio, exit load, SIP minimum, lock-in, riskometer, and benchmark from Groww pages for five HDFC Direct Growth funds. It does not advise, rank funds, or calculate returns.” Five quiet text tags, not buy cards: Large cap · Mid cap · Small cap · Gold ETF FoF · ELSS tax saver. Label “Try an example” then three equal-height question cards in a row with a mint left border: (1) What is the expense ratio of HDFC Large Cap Fund Direct Growth? (2) What is the exit load on HDFC Mid Cap Fund Direct Growth? (3) What is the lock-in period for HDFC ELSS Tax Saver Fund Direct Plan Growth? No assistant bubble yet. Send looks idle until there is text.

SCREEN 2 — Factual answer. Same chrome; example cards gone. Right-aligned user bubble: “What is the expense ratio of HDFC Large Cap Fund Direct Growth?” Left assistant card, mint badge “Answer”, body max 3 sentences: “On the loaded Groww page, HDFC Large Cap Fund — Direct Growth shows an expense ratio of 1.03. This assistant restates that published figure only.” Exactly one underlined mint link: “Groww — HDFC Large Cap Fund Direct Growth” (https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth). Muted 13px footer: “Last updated from sources: 2026-08-21”. No charts, no invest button.

SCREEN 3 — Advisory refusal. User: “Should I invest in HDFC Small Cap Fund?” Assistant card with amber left rail (#8A5A12 on #FBF3E6) and badge “Refused · not advice”. Exact body: “This assistant does not give investment advice or suitability views. It only restates facts published on Groww. Read Groww's guide to types of mutual funds.” Exactly one link: “Types of Mutual Fund in India” → https://groww.in/p/types-of-mutual-funds. Footer: “Last updated from sources: 2026-08-21”. Quiet line: “You can still ask a scheme fact, such as expense ratio or exit load.” Do not show TER, returns, or any small-cap number — a refusal must not look like a nudge to buy.

SCREEN 4 — Performance / factsheet only. User: “What returns did HDFC Large Cap Fund Direct Growth give last year?” Assistant card, blue badge “Scheme page only” (#1D4E89 on #EAF2FB). Body: “This assistant does not calculate or compare returns. Published performance is on this scheme's Groww page. Open that page for the latest figures.” One link to that scheme’s Groww page. Footer: “Last updated from sources: 2026-08-21”. Omit every percentage, CAGR, sparkline, bar chart, and NAV table.

SCREEN 5 — Loading then process. User: “How do I download a capital gains report?” First, an in-flight row: three-dot pulse “Looking up Groww help…”, send dimmed so it cannot double-submit. Then the answer card, badge “Process”: “Follow the steps on the cited Groww help page to download this report. This assistant restates published Groww process text only. It does not collect PAN, folio, or other account data.” One Groww help link “How to download capital gain report”. Footer: “Last updated from sources: 2026-08-21”. No upload dropzone, no PAN field.

SCREEN 6 — Mobile welcome (390×844). Same content as Screen 1. Disclaimer is a full-width mint strip under the top bar, still exactly “Facts-only. No investment advice.” — never hide it in a hamburger. Example questions stack as full-width cards. Composer sticky with safe-area padding. No Home/Portfolio/Invest tab bar.

Every assistant card: ≤3 sentences, exactly one groww.in link, last-updated footer. Large-cap TER mock is 1.03 (not 0.75). Editorial Indian fintech, not generic AI-chat chrome.
```
