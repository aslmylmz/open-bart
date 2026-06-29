---
title: 'Dynamic Hazard Rate BART: an open-source platform for calibration-sensitive behavioral risk assessment'
tags:
  - Python
  - React
  - psychometrics
  - behavioral economics
  - risk-taking
  - Balloon Analogue Risk Task
authors:
  - name: Ahmet Selim Yılmaz
    orcid: 0009-0000-2866-5774
    affiliation: 1
affiliations:
  - name: Middle East Technical University, Ankara, Türkiye
    index: 1
date: 20 June 2026
bibliography: paper.bib
---

# Summary

The Balloon Analogue Risk Task (BART) is one of the most widely used behavioral
measures of risk-taking [@lejuez2002]. In its standard form a balloon's burst
point is drawn once from a uniform distribution over its capacity $N$, which
places the expected-value (EV) optimal stopping point near $N/2$ — roughly 64
pumps on the highest-capacity balloon, while participants stop systematically
earlier. That gap is not a defect; it is a valid index of risk aversion. The
limitation that matters here is narrower: because the optimum is rarely
approached, pump count and earnings are nearly collinear, so the task cannot
separate calibrated risk-taking from gross exposure [@frey2017].

**Dynamic Hazard Rate BART** is an open-source platform that restores the
measurement of calibration. It replaces the single uniform draw with a sequence
of independent trials whose per-pump hazard increases linearly,
$P(\text{burst at pump } k) = k/N$. Under this model the EV-optimal stop is
approximately $\sqrt{N}$ — a reachable target — so the task can distinguish a
calibrated strategy from indiscriminate pumping and sort participants as cautious,
calibrated, or risk-seeking. The software comprises three parts: a
React/Next.js game client that administers a 30-balloon, three-hazard session and
logs pump-level telemetry; a Python scoring engine that derives more than thirty
psychometric metrics (EV calibration, learning and adaptation, post-explosion
adjustment, response consistency, and a narrative behavioral profile) with a
built-in session-validation pipeline; and Monte Carlo tooling that verifies the
analytically derived optima. It is released under the MIT license and archived on
Zenodo [@pydantic; @harris2020; @virtanen2020].

# Statement of need

A persistent obstacle in the psychology and economics of risk is the
attitude–behavior gap: self-reported risk preferences correlate only weakly with
behavioral tasks, and behavioral tasks correlate weakly with one another
[@frey2017; @pedroni2017]. A structural contributor to this gap is task design.
When the EV-optimal threshold is unreachable, the BART cannot reward calibration;
it can only index how far a participant pushed, not how well they calibrated.
Simulation work has shown that the hazard structure of a BART systematically
shapes the behavioral profiles it can
reconstruct [@diplinio2022], yet most deployed implementations retain the classic
uniform model, and reusable, openly documented scoring engines are scarce.

Dynamic Hazard Rate BART addresses three needs for researchers who study risk
behavior:

1. **A calibration-sensitive task.** The linear-hazard model has a closed-form,
   psychologically attainable optimum ($s^* \approx \sqrt{N}$), enabling the task
   to distinguish cautious, calibrated, and risk-seeking participants
   [@pleskac2008; @wallsten2005].
2. **A transparent, reusable scoring engine.** The engine computes EV-referenced
   calibration, learning, adaptation, and consistency metrics directly from raw
   event telemetry, with an explicit right-censoring (RNG-truncation) correction
   that uses collected balloons for all behavioral-intention metrics.
3. **Reproducibility and data quality.** A validation pipeline flags incomplete,
   too-fast, non-monotonic, automated, and key-repeat sessions, and a Monte Carlo
   script reproduces the analytic optima (11, 5, and 2 pumps for the three
   colors) and the earnings distribution that anchors the engine's efficiency
   metric.

The platform was built as the measurement instrument for a study at the Middle
East Technical University relating dynamic-hazard BART telemetry to the
domain-specific risk-taking (DOSPERT) scale [@weber2002; @blais2006] in a
laboratory and online sample, with a pre-registered external replication against
the open Basel–Berlin Risk Study [@frey2017]. Because the task, client, and
scoring engine are released together and openly documented, other researchers can
deploy, score, and analyze dynamic-hazard behavioral data without rebuilding the
infrastructure.

# Design and functionality

**The dynamic-hazard model.** The redesign targets the hazard structure. Rather
than treating risk as a bet on a fixed future state, it models risk-taking as
continuous adaptation to new information: pursuing a larger reward means pumping
further, which raises the per-pump hazard the participant faces. For a balloon of
capacity $N$, the probability of surviving $s$ pumps is
$\prod_{k=1}^{s}(1 - k/N)$, and the expected value of stopping at $s$ is
$\mathrm{EV}(s) = s\prod_{k=1}^{s}(1 - k/N)$. A second-order
expansion gives $\mathrm{EV}(s) \approx s\,e^{-s^2/2N}$, whose maximizer is
$s^* = \sqrt{N}$. The three colors (purple $N=128$, teal $N=32$, orange $N=8$)
have exact discrete optima of 11, 5, and 2 pumps. Each banked pump pays \$0.25, so
overshooting is penalized endogenously through forfeited earnings rather than an
arbitrary cap.

**Game client.** A self-contained React component (`app/src/BartGame.tsx`)
renders 30 balloons (10 per color, shuffled), implements the same $k/N$ hazard as
the engine, records high-resolution monotonic timestamps via `performance.now()`,
and submits a typed session payload to a scoring endpoint.

**Scoring engine.** The Python engine (`scoring/bart.py`) segments the event log
into balloons, excludes operating-system key-repeat artifacts, and computes
EV-ratio calibration (reward-weighted across hazard levels), an explosion penalty
reported separately from calibration, three learning estimators, within- and
between-balloon consistency, and a composite adaptive-strategy score, before
classifying the session into one of ten narrative risk styles. Input and output
are validated with pydantic models [@pydantic].

**Verification tooling.** `scripts/monte_carlo_ev.py` simulates 100,000 optimal
sessions to confirm the integer optima and to characterize the earnings
distribution; `scripts/generate_synthetic.py` produces synthetic datasets for
testing and demonstration. The numerical core relies on NumPy [@harris2020] and
SciPy [@virtanen2020].

Full documentation, including the metric definitions and the validation rules, is
available at the project's Read the Docs site.

# Acknowledgements

This work was conducted at the Middle East Technical University under the
supervision of Assoc. Prof. Gülşah Karakaya. The laboratory study was reviewed
and approved by the METU Human Subjects Ethics Committee (protocol
0176-ODTÜİAEK-2026).

# References
