# Installation

## Requirements

The scoring engine targets **Python 3.9+** and depends on a small scientific
stack:

| Package    | Minimum version | Used for                                   |
|------------|-----------------|--------------------------------------------|
| `numpy`    | 1.26            | vectorized metric computation              |
| `scipy`    | 1.12            | linear regression and correlation (`scipy.stats`) |
| `pydantic` | 2.6             | event and metric schema validation         |

Two scripts pull in optional extras:

| Package      | Minimum version | Used by                          |
|--------------|-----------------|----------------------------------|
| `matplotlib` | 3.8             | `scripts/monte_carlo_ev.py`      |
| `pandas`     | 2.2             | `scripts/generate_synthetic.py`  |

## From source

```bash
git clone https://github.com/aslmylmz/metu-risk-persona.git
cd metu-risk-persona
pip install -r requirements.txt
```

We recommend a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Verifying the install

The scoring engine is a plain Python package. From the repository root:

```bash
python -c "from scoring.bart import score_bart; print('ok')"
```

If that prints `ok`, you are ready to [score a session](quickstart.md).

```{admonition} Importing the package
:class: note

`scoring` is imported as a package relative to the repository root (for example
`from scoring.bart import score_bart`). Run your code from the repository root,
or add the repository root to `PYTHONPATH`, so that the `scoring` package can be
found.
```

## The game client

The React game client ([`app/src/BartGame.tsx`](game_client.md)) is a
standalone component bundled by Vite into a static SPA (it is not published as
an npm package). See
[Game client](game_client.md) for integration details, including the backend
endpoint it expects.

## Building the documentation locally

```bash
pip install -r docs/requirements.txt
sphinx-build -b html docs docs/_build/html
```

Open `docs/_build/html/index.html` in a browser.
