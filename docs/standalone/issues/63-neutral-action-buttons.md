# 63 — Neutral action buttons (drop the reward-priming emoji)

**Design-flaw · depends on: none**

Status: done

## Context

Cycle-02 audit finding F14 (D2). The gameplay action buttons carry emoji:

- `pumpButton: "🎈 Pump (Space)"` (`app/src/lib/i18n.ts:117`, and tr `:168`)
- `collectButton: "💰 Collect (Enter)"` (`i18n.ts:118`, tr `:169`)

The 💰 money-bag on **Collect** is a reward cue that can prime collecting, and emoji
generally add arousal/gaming affect. This works against the deliberately **sterile
Light Posture** (CONTEXT.md), whose purpose is to avoid the gaming-arousal confound
that biases risk-taking data — the same reason the participant UI is a plain
off-white instrument, not a game. The controls should stay measurement-neutral.

## Scope

- [ ] Remove the emoji from the action-button labels (both languages), keeping the
      keyboard hints (`Pump (Space)` / `Collect (Enter)`).
- [ ] If the glyphs are wanted for some deployments, make them an explicit opt-in
      rather than the default — but the default should be neutral text.

## Acceptance

- Default action-button labels are emoji-free in both languages (guarded by a string
  test); the keyboard-hint mapping is unchanged.
- `vitest`, `tsc --noEmit`, `vite build`, `pytest` stay green.

## Comments

Source: 2026-07-04 fresh full-audit, register row F14. Evidence: `i18n.ts:117-118`,
`:168-169`. Lowest-stakes item in the cycle and partly a judgment call — confirm the
neutrality reading is wanted before removing (some labs like the affordance). Webview-only.

**Done 2026-07-05. Decision (confirmed with the user): remove — neutral default,**
no opt-in flag. Dropped the emoji from the action-button labels: `🎈 Pump (Space)` →
`Pump (Space)`, `💰 Collect (Enter)` → `Collect (Enter)` (and the tr `Şişir (Boşluk)` /
`Topla (Enter)`), keeping the keyboard hints. No config surface, no schema change, no
re-freeze. Scope of the change was only the two button labels — the decorative balloon
🎈 stimulus (`BartGame.tsx`) and the debrief 🎈 are canonical BART surface (CONTEXT.md)
and were deliberately left.

Guards (`i18n.test.ts`, red before the change): en and tr `pumpButton`/`collectButton`
carry no emoji (`/\p{Extended_Pictographic}/u` — matches emoji but not ş/ı/ğ), plus a
positive lock that the Space→pump / Enter→collect keyboard-hint mapping is unchanged.
Four gates green (`vitest` 147, `tsc --noEmit`, `vite build`, `pytest` 182).
