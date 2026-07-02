---
title: 'Dynamic Hazard Rate BART: a configurable, offline desktop instrument for calibration-sensitive behavioral risk assessment'
tags:
  - Python
  - React
  - Tauri
  - psychometrics
  - behavioral economics
  - risk-taking
  - Balloon Analogue Risk Task
  - hazard functions
authors:
  - name: Ahmet Selim Yılmaz
    orcid: 0009-0000-2866-5774
    affiliation: 1
affiliations:
  - name: Middle East Technical University, Ankara, Türkiye
    index: 1
date: 2 July 2026
bibliography: paper.bib
---

# Summary

The Balloon Analogue Risk Task (BART) is one of the most widely used
behavioral measures of risk-taking [@lejuez2002]. In its classic form a
balloon's burst point is drawn once from a uniform distribution over its
capacity $N$, which places the expected-value (EV) optimal stopping point
near $N/2$ — so far above typical behavior that pump counts and earnings
become nearly collinear, and the task indexes gross risk exposure rather
than the *calibration* of risk to reward [@frey2017].

**Dynamic Hazard Rate BART** is an open-source desktop instrument that makes
the hazard structure itself an experimental design choice. A researcher
designs a study in a point-and-click interface — selecting, per balloon
color, one of eleven parameterized hazard families grounded in survival
analysis, with a live EV-curve preview — and runs participants through a
conventional BART flow entirely offline. The flagship *dynamic hazard*
model, $P(\text{burst at pump } k) = k/N$, moves the optimum to an
attainable $\approx \sqrt{N}$, so cautious, calibrated, and risk-seeking
strategies separate; the classic uniform model [@lejuez2002] and nine other
families (constant, Rayleigh, exponential, Weibull, Gompertz, logistic,
log-normal, step, and a validated tabular escape hatch) support baselines,
replications, and novel designs on the same instrument. Because arbitrary
hazards have no closed-form optimum, the engine computes each
configuration's optimum numerically from its survival curve and verifies it
by independent, seeded Monte Carlo simulation (\autoref{fig:families}).
Every session is scored locally into more than forty psychometric metrics
and exported as per-session telemetry plus a study-wide **Master CSV** ready
for SPSS or R.

![Expected-value curves for representative parameterizations of all eleven
hazard families (unit reward). Dots mark the numerically computed optima;
overlaid points are seeded Monte Carlo estimates
(`python -m scoring.verification` reproduces the verification
table).\label{fig:families}](hazard_families_ev.png)

# Statement of need

A persistent obstacle in the psychology and economics of risk is the
attitude–behavior gap: self-reported risk preferences correlate only weakly
with behavioral tasks, and behavioral tasks with one another
[@frey2017; @pedroni2017]. Simulation work shows that a BART's hazard
structure systematically shapes the behavioral profiles it can measure
[@diplinio2022], and cognitive models of the task make the stopping problem
central [@wallsten2005; @pleskac2008] — yet deployed implementations almost
universally hard-code one hazard, so comparing or replicating hazard
structures means rebuilding the task. Dynamic Hazard Rate BART treats the
hazard as a first-class, validated configuration axis: parameters only,
never code, with the classic design included as a baseline.

The second gap is deployment. Excellent open experiment platforms exist,
but they either target the browser and presume hosting infrastructure
[@deleeuw2015] or require scripting skills [@mueller2014] — while many
testing rooms run offline machines under strict data-protection and ethics
constraints. This instrument installs per-user from a double-click
installer, runs with **zero network access** (the scoring engine is a
loopback-only local process), needs no programming at any step, and ships
bilingual (English/Turkish) participant-facing screens. Data never leave
the machine, and outputs load directly into statistical software.

Finally, scoring is transparent and reusable: the Python engine computes
EV-referenced calibration (with the explosion penalty reported separately),
learning and adaptation estimators, consistency measures, per-color
breakdowns, and a narrative behavioral profile from raw pump-level
telemetry, with an explicit right-censoring correction that bases
behavioral-intention metrics on collected balloons only. A validation
pipeline flags incomplete, too-fast, non-monotonic, and automated sessions.
The platform originated as the measurement instrument for a study at the
Middle East Technical University relating BART telemetry to domain-specific
risk-taking (DOSPERT) [@weber2002; @blais2006], with a pre-registered
external replication against the Basel–Berlin Risk Study [@frey2017].

# Design and functionality

The instrument is a Tauri shell hosting a React/Vite interface, with the
scoring engine frozen by PyInstaller and supervised as a local FastAPI
sidecar; a strict offline content-security policy and a watchdog guarantee
the zero-network, no-orphan posture. Studies are portable `study.json`
files validated by the engine's configuration layer — a single `TaskConfig`
feeds the task, the live EV preview, the scoring, and the persisted config
snapshot, so every dataset is self-documenting. The numerical core uses
NumPy [@harris2020]; schemas are validated with pydantic [@pydantic]. The
scoring engine is also installable as a plain Python package, and its
numeric optima are guarded in continuous integration by the seeded
Monte Carlo sweep shown in \autoref{fig:families}. Documentation — a
non-coder researcher guide, a hazard-family reference, and a data-output
dictionary covering every Master CSV column — is maintained on Read the
Docs, and the repository is archived on Zenodo.

# Acknowledgements

This work was conducted at the Middle East Technical University under the
supervision of Assoc. Prof. Gülşah Karakaya. The laboratory study was
reviewed and approved by the METU Human Subjects Ethics Committee (protocol
0176-ODTÜİAEK-2026).

# References
