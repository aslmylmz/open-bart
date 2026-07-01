# Dark researcher view / light participant view — theme as role signal

The instrument uses two distinct color themes for its two audiences. The **Researcher View** (Study Setup, EV Preview) renders on a dark background (`#0f0f23` deep navy/charcoal). The **Participant View** (Consent, ID, Gameplay, Debrief) renders on a light background (`#f8f9fa` sterile off-white with dark text).

## Why not a single theme?

A unified dark theme was the default path — most of the existing inline styles (BartGame, Debrief) assumed dark backgrounds. But three concerns blocked it:

1. **Arousal confound.** In cognitive psychology, a dark "gaming" UI can act as a high-arousal prime, introducing an unwanted confound to behavioral risk-taking data. A sterile, light-mode background is the standard for validated clinical instruments (Lejuez et al. 2002; Pleskac 2008). The BART measures risk propensity — the UI must not prime it.

2. **Lab legibility.** Lab environments vary: fluorescent overhead lights, projectors, uncalibrated monitors. High-contrast dark text on a light background is readable under all of these. White-on-dark is not — it washes out under bright overhead lighting, exactly the condition most university labs have.

3. **Role signaling.** The researcher hands the machine to a participant. The transition from dark → light is a strong perceptual cue that the application has switched from "administrator tool" to "participant stimulus." This replaces what would otherwise be an easy-to-miss route change.

## Why dark for the researcher?

The researcher works privately on their own machine, often in an office setting. A dark theme makes the SVG expected-value curves highly readable (colored lines against dark canvas), gives validation error lists visual contrast, and communicates a premium analytical-tool feel. This follows Apple Human Interface Guidelines conventions for professional creative/analytical tools.

## Alternatives considered

- **All light.** Simpler, but the researcher view loses the premium feel, and the mode switch loses its perceptual punch.
- **All dark.** The gaming-prime confound is a real methodological risk for a published research instrument.
- **User-selectable theme.** Overcomplicated for a research instrument where the theme carries methodological weight, not just preference.
