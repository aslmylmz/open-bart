# Dynamic Hazard Rate BART

**A configurable, offline desktop instrument for the Balloon Analogue Risk Task.**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20592164.svg)](https://doi.org/10.5281/zenodo.20592164)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation Status](https://readthedocs.org/projects/open-bart/badge/?version=latest)](https://open-bart.readthedocs.io/en/latest/?badge=latest)

Dynamic Hazard Rate BART lets a research lab administer, score, and export
[Balloon Analogue Risk Task](https://doi.org/10.1037/1076-898X.8.2.75) (BART)
sessions **without writing code and without a network connection**. A
researcher designs a study in a point-and-click Study Setup screen — choosing
from a curated library of [eleven hazard families](hazard_families.md) with a
live expected-value preview — and runs participants through a conventional
BART flow. Sessions are scored locally by the bundled Python engine and
written to [per-session files plus a shared Master CSV](data_outputs.md)
ready for SPSS or R.

The flagship paradigm is the **dynamic hazard rate**: at each pump $k$ the
balloon bursts with probability $k / N$ (a sequence of independent trials
with a linearly increasing hazard). This moves the expected-value (EV)
optimal stopping point from the unattainable $N/2$ of the classic task down
to roughly $\sqrt{N}$ — a target participants can actually reach — so the
task distinguishes **cautious**, **calibrated**, and **reckless** play
rather than collapsing into a one-dimensional proxy for raw risk exposure.
The classic uniform (Lejuez) model and nine other hazard families are
available as configuration choices for baselines and replications.

The project comprises:

- the **standalone desktop instrument** (Tauri shell + React/Vite UI + a
  loopback-only Python scoring sidecar; see the
  [researcher quickstart](standalone/quickstart.md)),
- a reusable **Python scoring engine** ([`scoring/`](scoring_engine.md)) that
  derives 40+ psychometric metrics from raw event telemetry, and
- **Monte Carlo verification tooling** that confirms every configuration's
  numerically computed EV optima ([hazard-family reference](hazard_families.md)).

It was developed as the measurement instrument for a research program at the
Middle East Technical University (METU).

```{admonition} Where to start
:class: tip

Running a study? Follow the [researcher quickstart](standalone/quickstart.md),
then see [Data Outputs](data_outputs.md) for what lands in your output
directory. Using the engine as a library? Read [Task Design](task_design.md)
for the model, then [Quick Start](quickstart.md) to score your first session.
Looking for a specific number? Jump to the
[Metrics Reference](metrics_reference.md).
```

## The default study

Out of the box the instrument loads the validated three-color linear-hazard
design — 30 balloons (10 per color) in shuffled order, deliberately neutral
colors (no red/green danger framing), $0.25 per banked pump. Every element
below is configurable in Study Setup.

| Color  | Max pumps ($N$) | Risk tier | EV-optimal stop ($s^*$) | Peak EV  | $P(\text{survive } s^*)$ |
|--------|:---------------:|-----------|:-----------------------:|:--------:|:------------------------:|
| Purple | 128             | Low       | 11                      | 6.46     | 0.59                     |
| Teal   | 32              | Medium    | 5                       | 3.04     | 0.61                     |
| Orange | 8               | High      | 2                       | 1.31     | 0.66                     |

## Contents

```{toctree}
:maxdepth: 2
:caption: For researchers

Researcher quickstart <standalone/quickstart>
Multi-station studies <standalone/multi_station>
SmartScreen & antivirus <standalone/SMARTSCREEN>
Kiosk mode & OS lockdown <standalone/KIOSK>
hazard_families
data_outputs
```

```{toctree}
:maxdepth: 2
:caption: The engine as a library

installation
quickstart
```

```{toctree}
:maxdepth: 2
:caption: The task & engine

task_design
scoring_engine
validation
metrics_reference
```

```{toctree}
:maxdepth: 2
:caption: Components & tooling

game_client
schemas
scripts
```

```{toctree}
:maxdepth: 2
:caption: Reference

api
references
```

## Citing this software

If you use this instrument in your research, please cite the archived
release (see [CITATION.cff](https://github.com/aslmylmz/open-bart/blob/main/CITATION.cff)):

> Yılmaz, A. S. (2026). *Dynamic Hazard Rate BART: A Configurable Offline
> Desktop Instrument for the Balloon Analogue Risk Task* (Version 1.2.1)
> [Computer software]. <https://doi.org/10.5281/zenodo.20592164>

## License

Released under the [MIT License](https://github.com/aslmylmz/open-bart/blob/main/LICENSE).
