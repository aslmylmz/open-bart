# 24 — Global CSS stylesheet + dark theme foundation

**UI · depends on: none (standalone)**

## Context

The BART instrument has **no CSS file at all**. Every screen renders with
browser-default styling: system serif font, white/light-gray background, unstyled
`<input>`, `<select>`, `<button>`, and `<fieldset>` elements. Some components
(BartGame, Debrief) use inline styles designed for a dark background — but since the
page background is browser-default light gray, white text is invisible and
glassmorphism cards (`rgba(255,255,255,0.03)`) render as transparent.

The app references utility CSS classes (`flex`, `flex-col`, `items-center`, `text-5xl`,
etc.) in BartGame.tsx and Debrief.tsx, but these classes are **never defined** — they
only worked coincidentally from Tailwind remnants or not at all.

## Scope

- [ ] [app/src/index.css](../../../app/src/index.css) **[NEW]**: create a comprehensive
  global stylesheet that:
  - Resets `box-sizing`, `margin`, `padding` on `*`
  - Sets dark background (`#0f0f23` → `#1a1a2e` gradient or similar) on `html`/`body`
  - Sets default font to the system sans-serif stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`) to comply with the offline CSP requirement (ADR 0002).
  - Styles all form controls (`input`, `select`, `button`, `fieldset`, `legend`) with
    dark-theme treatment: dark backgrounds, subtle borders, rounded corners, focus rings
  - Provides the utility classes already referenced in JSX: `.flex`, `.flex-col`,
    `.items-center`, `.gap-6`, `.py-8`, `.py-10`, `.py-16`, `.text-5xl`, `.text-6xl`,
    `.w-full`
  - Adds the `@keyframes fadeIn` animation BartGame.tsx references
  - Styles dark-theme scrollbars
- [ ] [app/src/main.tsx](../../../app/src/main.tsx): add `import "./index.css";` at the
  top so the stylesheet is loaded.

## Acceptance

- Opening `http://localhost:5173` shows a dark-themed page with the system sans-serif font.
- All form controls (inputs, selects, buttons, fieldsets) are styled and readable.
- The utility classes used by BartGame/Debrief render correctly (flex layout, padding).
- Existing tests stay green: `npm test`, `pytest`.
