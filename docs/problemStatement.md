# Problem Statement: Mutual Fund FAQ Assistant (Facts-Only Q&A)

This document is the canonical project context for the Mutual Fund FAQ Assistant. It is derived from `docs/problemStatement.txt` and should be treated as the source of requirements for design, implementation, and evaluation.

---

## 1. Overview

Build a **facts-only FAQ assistant** for mutual fund schemes, using **Groww as the reference product context** (UX and query patterns), not as a data source.

The assistant answers **objective, verifiable** queries about mutual funds by retrieving information **exclusively from official public sources**:

- AMC (Asset Management Company) websites
- AMFI (Association of Mutual Funds in India)
- SEBI (Securities and Exchange Board of India)

The system must **never** provide investment advice, opinions, or recommendations. Every response must include **a single, clear source link** and follow the constraints on clarity, accuracy, and compliance defined below.

**North star:** accuracy over intelligence. Users receive only verified, source-backed financial information, with no advisory bias or speculative content.

---

## 2. Objective

Design and implement a lightweight **Retrieval-Augmented Generation (RAG)** assistant that:

1. Answers factual queries about mutual fund schemes
2. Uses a curated corpus of official documents
3. Provides concise, source-backed responses

---

## 3. Target Users

| User | Need |
| --- | --- |
| Retail investors comparing mutual fund schemes | Fast, verifiable facts (expense ratio, exit load, SIP minimums, lock-in, riskometer, benchmark) |
| Customer support and content teams | Repeatable answers to common mutual fund FAQs without giving advice |

---

## 4. Product and Compliance Positioning

| Allowed | Not allowed |
| --- | --- |
| Facts from official AMC / AMFI / SEBI documents | Investment advice, opinions, or recommendations |
| Short answers with exactly one citation | Performance comparisons or return calculations |
| Polite refusal of advisory questions | Third-party blogs or aggregator sites as sources |
| Educational link on refusal (AMFI / SEBI) | Collecting PAN, Aadhaar, account numbers, OTPs, email, or phone |

**Visible product disclaimer (UI):**

> Facts-only. No investment advice.

---

## 5. Scope of Work

### 5.1 Corpus definition

**Selected AMC:** HDFC Mutual Fund (inferred from the Groww scheme URLs in the brief).

**Scheme count:** 5 schemes, with category diversity (large-cap, mid-cap, small-cap, gold FoF, ELSS).

Groww URLs below are **reference product pages** for scheme identity and typical FAQ framing. **Corpus and citations must come from official AMC / AMFI / SEBI sources**, not Groww, blogs, or aggregators.

| # | Scheme (from Groww slug) | Category | Groww reference URL |
| --- | --- | --- | --- |
| 1 | HDFC Mid Cap Fund — Direct Growth | Mid-cap | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth |
| 2 | HDFC Small Cap Fund — Direct Growth | Small-cap | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| 3 | HDFC Gold ETF Fund of Fund — Direct Plan Growth | Gold ETF FoF | https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth |
| 4 | HDFC Large Cap Fund — Direct Growth | Large-cap | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| 5 | HDFC ELSS Tax Saver Fund — Direct Plan Growth | ELSS | https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth |

**Corpus expectations:**

- Curated official documents only (scheme information documents, factsheets, KIM, SID/SAI as applicable, AMFI/SEBI pages)
- Cover the fact types listed in §5.2 for all five schemes
- Track a **last-updated-from-sources** date for every answer

### 5.2 FAQ assistant requirements

The assistant must answer **facts-only** queries, including but not limited to:

- Expense ratio of a scheme
- Exit load details
- Minimum SIP amount
- ELSS lock-in period
- Riskometer classification
- Benchmark index
- Process to download statements or capital gains reports

**Response format (hard rules):**

| Rule | Requirement |
| --- | --- |
| Length | Maximum **3 sentences** |
| Citations | Exactly **one** citation link |
| Footer | `Last updated from sources: <date>` |

### 5.3 Refusal handling

The assistant must refuse **non-factual or advisory** queries, for example:

- “Should I invest in this fund?”
- “Which fund is better?”

Refusal responses must:

- Be polite and clearly worded
- Reinforce the **facts-only** limitation
- Provide a relevant **educational** link (e.g. AMFI or SEBI resource)

Refusal still follows the product spirit: no advice, no comparison ranking, no implied recommendation.

### 5.4 User interface (minimal)

The UI must include:

1. A **welcome message**
2. **Three example questions**
3. A **visible disclaimer:** `Facts-only. No investment advice.`

Keep the interface clean, minimal, and user-friendly.

---

## 6. Constraints

### 6.1 Data and sources

- Use **only** official public sources: AMC, AMFI, SEBI
- **Do not** use third-party blogs or aggregator websites as retrieval sources or citations
- Groww is **product-context reference only**, not an allowed fact source

### 6.2 Privacy and security

Do **not** collect, store, or process:

- PAN or Aadhaar numbers
- Account numbers
- OTPs
- Email addresses or phone numbers

### 6.3 Content restrictions

- No investment advice or recommendations
- No performance comparisons or return calculations
- For **performance-related** queries: provide a link to the **official factsheet only** (do not compute or compare returns)

### 6.4 Transparency

- Responses must be short, factual, and verifiable
- Every answer must include a **source link** and a **last updated** date

---

## 7. Architecture intent (RAG)

The brief requires a **lightweight RAG** approach:

1. **Ingest** a small, curated corpus of official documents for the five HDFC schemes (plus AMFI/SEBI pages needed for process/education facts)
2. **Retrieve** the most relevant official passage(s) for the user question
3. **Generate** a facts-only answer constrained to 3 sentences, one citation, and the last-updated footer
4. **Refuse** advisory / comparison / PII / out-of-scope questions with a polite facts-only message and one educational official link

Implementation details (chunking, embeddings, vector store, LLM, UI stack) are not specified in the original brief and may be chosen as long as they stay lightweight and satisfy the constraints above.

---

## 8. Expected deliverables

### 8.1 README

Must include:

- Setup instructions
- Selected AMC and schemes
- Architecture overview (RAG approach)
- Known limitations

### 8.2 Disclaimer snippet

```
Facts-only. No investment advice.
```

This snippet must appear in the UI and may be reused in README / about copy.

### 8.3 Application

A working minimal FAQ assistant that meets the success criteria in §9.

---

## 9. Success criteria

| Criterion | Meaning |
| --- | --- |
| Accurate retrieval | Factual mutual fund information matches official sources |
| Facts-only adherence | No advice, opinions, rankings, or return math |
| Valid citations | Every answer has exactly one official source link |
| Proper refusals | Advisory and comparison queries are refused with an educational official link |
| UX | Clean, minimal, user-friendly UI with welcome, 3 examples, and disclaimer |

---

## 10. Out of scope (implied by the brief)

- Personalized portfolio advice or “suitability” for a user
- Multi-AMC coverage beyond the selected HDFC schemes
- Login, KYC, or any PII capture
- Using Groww, Value Research, Morningstar, or similar aggregators as ground truth
- Computing or comparing historical / expected returns
- Long-form educational essays (answers stay ≤ 3 sentences)

---

## 11. Example interaction contract

**Factual (must answer):**

> What is the expense ratio of HDFC Large Cap Fund Direct Growth?

Expected shape:

1. Up to 3 factual sentences
2. Exactly one official citation URL
3. Footer: `Last updated from sources: <date>`

**Advisory (must refuse):**

> Should I invest in HDFC Small Cap Fund?

Expected shape:

1. Polite refusal
2. Restate facts-only limitation
3. One AMFI or SEBI educational link

**Performance (must not calculate):**

> What returns did this fund give last year?

Expected shape: do not compute or compare returns; point to the **official factsheet** only.

---

## 12. Source file

Original brief: `docs/problemStatement.txt`
