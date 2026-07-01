# 27 — BartGame gameplay + finished screen layout fixes

**UI · depends on: 24**

## Context

The balloon gameplay screen has some inline styling (gradient Pump/Collect buttons,
balloon shape) but suffers from serious layout issues:

- The balloon counter shows "Balloon /30" with a missing current number
- Pump and Collect buttons are left-aligned instead of centered under the balloon
- The bottom half of the screen is dead empty space
- "← Back to setup" is a raw system button at the top (and arguably should not be
  visible during a live task to prevent accidental exits)
- The "finished" screen's completed-balloons dot track is functional but cramped
- The "See Results" button on the finished screen works but sits among unstyled
  surroundings

## Scope

- [ ] [app/src/BartGame.tsx](../../../app/src/BartGame.tsx): implement the **Gameplay Layout** spec (Light Posture):
  - **Background**: Ensure the screen uses the `#f8f9fa` light background with high-contrast text.
  - **Top Bar**: Small, understated gray counter. Fix the counter to show current number (`Balloon 1/30` left, `Total $X` right).
  - **Balloon**: Center the gameplay layout vertically in the viewport. The balloon should be the largest element with NO text inside it.
  - **Current earnings**: Add a large, static, bold counter below the balloon (`Current: $X`).
  - **Buttons**: Center the Pump/Collect buttons below the earnings (currently left-aligned). Keep them standard-sized and neutral. Keyboard hints are already on the labels.
  - **Progress dots**: Move the completed-balloons dot track to the bottom, horizontal timeline style.
  - **Finished screen**: Proper vertical centering, styled "See Results" CTA.
  - Consider hiding or making the "← Back to setup" button less prominent during active
    gameplay (prevent accidental exits).

## Acceptance

- The screen uses the Light Posture (white/light-gray background, dark text).
- The balloon, earnings counter, buttons, and dot track are all horizontally centered and vertically stacked.
- The balloon counter shows e.g. "Balloon 3/30" (not "Balloon /30").
- The current earnings ($ amount) is displayed *outside* and below the balloon, not inside it.
- The finished screen is vertically centered with a prominent "See Results" button.
- Layout looks good at 1280×800 (the Tauri window default) and 1200×870.
- Existing tests stay green.
