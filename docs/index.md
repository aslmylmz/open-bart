# Dynamic Hazard Rate BART

**A multi-risk Balloon Analogue Risk Task.**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20592164.svg)](https://doi.org/10.5281/zenodo.20592164)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation Status](https://readthedocs.org/projects/metu-risk-persona/badge/?version=latest)](https://metu-risk-persona.readthedocs.io/en/latest/?badge=latest)

Dynamic Hazard Rate BART is an open-source implementation of a modified
[Balloon Analogue Risk Task](https://doi.org/10.1037/1076-898X.8.2.75) (BART) that
replaces the classic uniform burst threshold with a **dynamic hazard rate**: at
each pump $k$, the balloon bursts with probability $k / N$ (a sequence of
independent trials with a linearly increasing hazard). This single
change moves the expected-value (EV) optimal stopping point from the
unattainable $N/2$ of the standard task down to roughly $\sqrt{N}$ — a target
that ordinary participants can actually reach. As a result the task can
distinguish **cautious**, **calibrated**, and **reckless** play rather than
collapsing into a one-dimensional proxy for raw risk exposure.

The repository bundles three things:

- a complete **React / Vite game client** ([`app/src/BartGame.tsx`](game_client.md)),
- a **Python scoring engine** ([`scoring/bart.py`](scoring_engine.md)) that derives
  more than thirty psychometric metrics from raw event telemetry, and
- **Monte Carlo verification tooling** ([`scripts/`](scripts.md)) that confirms the
  analytically derived EV-optimal stops.

It was developed as the measurement instrument for a research study at the
Middle East Technical University (METU). The live platform is hosted at
[bart.aselimyilmaz.com](https://bart.aselimyilmaz.com).

```{admonition} Where to start
:class: tip

New here? Read [Task Design](task_design.md) for the model and its mathematics,
then [Quick Start](quickstart.md) to score your first session. Looking for a
specific number? Jump to the [Metrics Reference](metrics_reference.md).
```

## Three-color risk profiles

A session is 30 balloons — 10 of each color — presented in a shuffled order.
The colors are deliberately neutral (no red/green) to avoid danger/safety
framing.

| Color  | Max pumps ($N$) | Risk tier | EV-optimal stop ($s^*$) | Peak EV  | $P(\text{survive } s^*)$ |
|--------|:---------------:|-----------|:-----------------------:|:--------:|:------------------------:|
| Purple | 128             | Low       | 11                      | 6.46     | 0.59                     |
| Teal   | 32              | Medium    | 5                       | 3.04     | 0.61                     |
| Orange | 8               | High      | 2                       | 1.31     | 0.66                     |

Each collected pump is worth **\$0.25**; a burst forfeits the whole balloon.

## Contents

```{toctree}
:maxdepth: 2
:caption: Getting started

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

If you use this implementation in your research, please cite the archived
release (see [CITATION.cff](https://github.com/aslmylmz/metu-risk-persona/blob/main/CITATION.cff)):

> Yılmaz, A. S. (2026). *Dynamic Hazard Rate BART: A Multi-Risk Balloon Analogue
> Risk Task* (Version 0.1.2) [Computer software].
> <https://doi.org/10.5281/zenodo.20592164>

## License

Released under the [MIT License](https://github.com/aslmylmz/metu-risk-persona/blob/main/LICENSE).
