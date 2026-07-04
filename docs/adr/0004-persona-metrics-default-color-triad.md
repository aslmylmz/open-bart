# Persona metrics are validated only for the default color triad

> **Status update — resolved by issue 56 (done).** The generalization deferred in
> step 2 below has landed: the name-keyed persona metrics now resolve behavior by
> *risk role* — the study's colors ranked by EV-optimal stop (safest = highest
> optimum, riskiest = lowest), with the two-color contrasts run between the safest
> and riskiest color — instead of by the literal names `purple`/`teal`/`orange`.
> Any color set now scores coherently, so the guard-and-document `session_warnings`
> entry (step 1) was removed. The default purple/teal/orange study is byte-identical,
> pinned by a golden-snapshot regression test. The record below is preserved for the
> history of the decision.

The scoring engine draws two kinds of output from a session. **EV-based metrics**
(risk calibration, EV-efficiency uniformity, explosion penalty, risk adjustment,
per-color breakdown) are computed from each color's precomputed survival/EV curve
and are **fully config-agnostic** — they hold for any color names, counts, caps,
and hazard families. **Name-keyed persona metrics** (the learning-rate family,
color discrimination, `patience_index`, `orange_avg_pumps`, and several
`risk_style` branches) resolve behavior by the *literal* color names
`purple` / `teal` / `orange` and their low/medium/high semantics.

The persona layer is therefore validated only for the default color triad. A
study that renames its colors (or drops `purple` / `orange`) gets those name-keyed
fields silently degraded to `0`/`None` — populated-looking but meaningless.

## Decision

Close the *silent* failure now, defer the deeper fix:

1. **Guard-and-document (this change, issue 51).** `score_bart` appends an
   explicit `session_warnings` entry when the study uses any color name outside
   the recognized set, naming which metrics are unreliable and which remain
   valid. Nothing is excluded; scoring math is unchanged; the default study is
   byte-identical.
2. **Full generalization is deferred to issue 56.** Rewiring the name-keyed
   metrics onto config-declared risk ordering (rank by cap / EV-optimal) so any
   color set scores coherently is a larger change across the whole persona layer,
   and must prove default-study output is unchanged. It is tracked separately.

## Why record this

The instrument advertises 11 hazard families and fully configurable color
profiles, so a researcher will reasonably assume every scored field is valid for
their custom study. This ADR marks the boundary: "configurable" currently means
the task, the curves, and the EV-based metrics — **not** the name-keyed persona
layer. A contributor extending the persona metrics must either keep them keyed to
the recognized names or complete the issue-56 generalization; they must not let a
renamed-color study publish persona fields without the warning.

## Considered alternative

Do the full generalization (issue 56) immediately instead of the guard. Rejected
for now because it touches most of the persona layer at once, carries real
regression risk to the validated default-study numbers, and the honest warning
closes the dangerous case (silently-wrong published data) in a small, reviewable
slice. The generalization remains the intended end state, not a rejected one.
