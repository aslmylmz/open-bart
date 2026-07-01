# 25 — StudySetup + EvPreview styling

**UI · depends on: 24**

## Context

The researcher-facing Study Setup form and EV preview render entirely with browser
defaults. Inputs flow inline with labels, fieldsets have thin gray browser borders,
buttons are unstyled system buttons, and the EV preview SVGs sit in bare `1px solid
#ddd` boxes. The form is functional but looks like raw HTML from the 1990s.

## Scope

- [ ] [app/src/setup/StudySetup.tsx](../../../app/src/setup/StudySetup.tsx): restyle the
  form with:
  - Proper card container with heading
  - CSS grid or flex layout for form fields (labels above inputs, not inline beside)
  - Color fieldsets get a left-border accent matching the balloon's `display_hex`
  - "Save study…" / "Load study…" buttons styled consistently with dark theme
  - Error list styled with proper red accent
  - Section headings ("Colors") with proper typography and spacing
- [ ] [app/src/setup/EvPreview.tsx](../../../app/src/setup/EvPreview.tsx): restyle with:
  - SVG plots get a dark background with rounded corners (not bare white)
  - Figure captions get proper typography
  - Legend styled as a subtle footer
- [ ] [app/src/App.tsx](../../../app/src/App.tsx): "Start run →" button gets consistent
  dark-theme styling; overall layout wrapper with proper min-height and centering.

## Acceptance

- The Study Setup form is readable, well-spaced, and visually professional on the dark
  background.
- Color fieldsets are visually distinguished by their balloon color.
- EV preview plots are readable on the dark background.
- "Start run →" button is styled and prominent.
- Existing tests stay green.
