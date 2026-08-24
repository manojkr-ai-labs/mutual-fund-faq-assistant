---
name: Mutual Fund FAQ Assistant
colors:
  surface: '#e9fef5'
  surface-dim: '#cadfd6'
  surface-bright: '#e9fef5'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#e3f8ef'
  surface-container: '#def3ea'
  surface-container-high: '#d8ede4'
  surface-container-highest: '#d2e7de'
  on-surface: '#0d1f1a'
  on-surface-variant: '#3d4a42'
  inverse-surface: '#22342e'
  inverse-on-surface: '#e1f5ec'
  outline: '#6d7a71'
  outline-variant: '#bccac0'
  surface-tint: '#006c49'
  primary: '#006947'
  on-primary: '#ffffff'
  primary-container: '#00855b'
  on-primary-container: '#f5fff6'
  inverse-primary: '#63dca6'
  secondary: '#51625a'
  on-secondary: '#ffffff'
  secondary-container: '#d4e7dd'
  on-secondary-container: '#576860'
  tertiary: '#595d5b'
  on-tertiary: '#ffffff'
  tertiary-container: '#717574'
  on-tertiary-container: '#fafdfb'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#81f9c1'
  primary-fixed-dim: '#63dca6'
  on-primary-fixed: '#002113'
  on-primary-fixed-variant: '#005236'
  secondary-fixed: '#d4e7dd'
  secondary-fixed-dim: '#b8cbc1'
  on-secondary-fixed: '#0f1f19'
  on-secondary-fixed-variant: '#3a4a43'
  tertiary-fixed: '#e0e3e1'
  tertiary-fixed-dim: '#c4c7c5'
  on-tertiary-fixed: '#181c1b'
  on-tertiary-fixed-variant: '#434846'
  background: '#e9fef5'
  on-background: '#0d1f1a'
  surface-variant: '#d2e7de'
typography:
  display-lg:
    fontFamily: Fraunces
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Fraunces
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  headline-sm:
    fontFamily: Fraunces
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  label-caps:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  display-lg-mobile:
    fontFamily: Fraunces
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  max_width_content: 720px
  gutter: 24px
  stack_sm: 8px
  stack_md: 16px
  stack_lg: 32px
  control_height: 44px
  safe_area_bottom: 24px
---

## Brand & Style
The design system is centered on "Editorial FinTech"—a hybrid of high-end publishing and modern financial utility. The target audience is the informed Indian investor seeking clarity over noise. The aesthetic leverages **Minimalism** with **Modern Corporate** influences, prioritizing extreme legibility and a sense of calm authority. 

The emotional response should be one of "quiet confidence." By removing all transactional "buy" buttons and market volatility charts, the UI transforms from a trading tool into a trusted advisor. The use of a sage-tinted canvas instead of pure white reduces eye strain and establishes a premium, deliberate atmosphere.

## Colors
The palette is rooted in nature-inspired neutrals and professional accents.
- **Primary (Mint):** Used sparingly for interactive states and the global disclaimer pill.
- **Ink & Muted Text:** High-contrast #12221C for body text ensures readability, while #5C6F68 handles secondary metadata.
- **The Rails:** Specific semantic colors are reserved for message types. The **Info Rail** (Blue) denotes factual citations, while the **Refusal Rail** (Amber) marks boundary-setting responses (e.g., "I cannot provide personalized investment advice").
- **Canvas:** The #F4F7F5 background acts as the "desk" upon which white "paper" cards are placed.

## Typography
This design system employs a serif-for-structure and sans-for-utility approach. 
- **Headlines:** Fraunces provides an authoritative, editorial feel. Use it for article titles, major section headers, and the assistant's primary response headers.
- **Body & UI:** Plus Jakarta Sans is used for all conversational text, input fields, and labels to maintain a contemporary, tech-forward efficiency.
- **Line Height:** Generous leading (1.6x for body) is mandatory to facilitate long-form reading of complex financial concepts.

## Layout & Spacing
The layout follows a **Fixed Column** philosophy. 
- **The Conversation Rail:** All content is centered in a 720px wide column on desktop to prevent eye fatigue.
- **Margins:** 24px horizontal padding on mobile, scaling to auto-center on desktop.
- **Rhythm:** Use a strict 8px grid. Elements within cards use 16px padding, while spacing between distinct user/assistant messages is 32px.
- **Sticky Zones:** The navigation header (64px height) and the input composer (dynamic height with 44px min-control) remain fixed to ensure the assistant is always reachable.

## Elevation & Depth
The system uses **Tonal Layering** over shadows. 
- **Level 0 (Canvas):** #F4F7F5 (Sage) background.
- **Level 1 (Surface):** #FFFFFF (Paper) cards with a 1px #D7E2DC (Hairline) border. 
- **Interactive Depth:** Only the primary input field and active cards receive a very soft, diffused shadow (0px 4px 20px rgba(18, 34, 28, 0.04)) to indicate focus. 
- **The Hairline:** Most hierarchy is established by the 1px border. Do not use heavy drop shadows; the goal is a flat, printed-matter aesthetic.

## Shapes
A consistent **14px corner radius** is applied to all primary containers, including assistant message cards, user bubbles, and the bottom composer. 
- **Exceptions:** Smaller components like tags or "Pill" indicators (e.g., the disclaimer pill) use a fully rounded (999px) radius. 
- **Input Fields:** Maintain the 14px radius to match cards, creating a unified language of "soft rectangles."

## Components
- **Assistant Message Cards:** White background, 14px radius, 1px hairline border. Must include a 4px solid left-border "rail." Use Blue #1D4E89 for factual answers and Amber #8A5A12 for refusals/warnings.
- **User Bubbles:** Mint-soft #E6F6EF background, no border, right-aligned. Text color remains Ink #12221C.
- **The Disclaimer Pill:** A persistent Mint #0E9F6E pill in the navigation bar with white 12px caps text: "EDUCATIONAL PURPOSE ONLY".
- **Composer:** A fixed bottom bar containing a 44px height text input. The "Send" action should be a simple icon or text link, avoiding heavy button styling to keep the focus on the conversation.
- **Source Tags:** Small 1px bordered boxes at the bottom of assistant responses to link to SEBI guidelines or fund prospectuses.
- **Lists:** Unordered lists within assistant messages should use Mint-colored dots.