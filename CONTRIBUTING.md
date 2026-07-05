# Contributing

Thanks for your interest in the Dynamic Hazard Rate BART. Contributions,
bug reports, and feature requests are all welcome.

## Code of Conduct

This project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating,
you are expected to uphold this code. Please report unacceptable behavior to the project
maintainers.

## Getting help and reporting issues

- **Questions and support:** open a
  [GitHub Discussion](https://github.com/aslmylmz/metu-risk-persona/discussions)
  or an issue with the `question` label.
- **Bug reports:** open a
  [GitHub Issue](https://github.com/aslmylmz/metu-risk-persona/issues). Please
  include your Python version, the package versions from `pip freeze`, a minimal
  event log that reproduces the problem, and the actual vs. expected output.
- **Feature requests:** open an issue describing the use case and, where
  relevant, the psychometric or methodological motivation.

## Development setup

```bash
git clone https://github.com/aslmylmz/metu-risk-persona.git
cd metu-risk-persona
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest          # for the test suite
```

## Running the tests

The test suite lives in [`tests/`](tests/) and runs against the scoring engine.
From the repository root:

```bash
pytest
```

Please add or update tests for any change to the scoring logic, the validation
pipeline, or the schemas, and make sure the full suite passes before opening a
pull request.

## Building the documentation

```bash
pip install -r docs/requirements.txt
sphinx-build -b html docs docs/_build/html
```

## Pull requests

1. Fork the repository and create a topic branch.
2. Keep changes focused; one logical change per pull request.
3. Match the surrounding code style. The Python code targets 3.9+, uses type
   hints, and follows the existing naming and docstring conventions.
4. If you change a metric definition or a validation rule, update the
   corresponding page under `docs/` so the documentation stays accurate.
5. Ensure `pytest` passes and the docs build cleanly.
6. Open the pull request with a clear description of *what* changed and *why*.

## Scope and design notes

- All behavioral-intention metrics are computed from **collected (non-exploded)**
  balloons to avoid right-censoring (RNG-truncation) bias. Preserve this
  invariant when adding metrics.
- The expected-value optima (11 / 5 / 2 pumps for purple / teal / orange) are
  derived from the sequential model in `scoring/bart.py`; if you change
  the color profiles, re-derive them and update both the engine and the docs.
- Real participant data is **never** committed. Only synthetic data (under
  `data/synthetic/`) belongs in the repository.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE) that covers the project.
