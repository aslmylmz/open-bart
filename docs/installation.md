# Installation

## Requirements

```{admonition} Running studies? You don't need Python.
:class: tip

This page is for using the **scoring engine as a Python library**. To run
studies with the desktop instrument, download the installer instead — see the
[researcher quickstart](standalone/quickstart.md).
```

The scoring engine targets **Python 3.9+** with a deliberately small core
(the engine is scipy-free so the frozen desktop sidecar stays lean):

| Package    | Minimum version | Used for                           |
|------------|-----------------|------------------------------------|
| `numpy`    | 1.26            | vectorized metric computation      |
| `pydantic` | 2.6             | event and metric schema validation |

Optional extras (`pip install -e ".[scripts]"`) pull in `matplotlib`,
`pandas`, and `scipy` for the figure/data [scripts](scripts.md).

## From source

```bash
git clone https://github.com/aslmylmz/open-bart.git
cd open-bart
pip install -e .
```

We recommend a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

## Verifying the install

The scoring engine is a plain Python package. From the repository root:

```bash
python -c "from scoring.bart import score_bart; print('ok')"
```

If that prints `ok`, you are ready to [score a session](quickstart.md).

```{admonition} Importing the package
:class: note

The editable install (`pip install -e .`) registers the `scoring` package, so
`from scoring.bart import score_bart` works from anywhere in the environment.
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
