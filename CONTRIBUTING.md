# Contributing

Contributions that make CBOM easier to use, understand and verify are welcome.
Open an [issue](https://github.com/monurkeskin/CBOM/issues) for a bug or a proposed
change to model assumptions before making a large algorithm revision.

## Local setup

Use Python 3.10 or newer in an isolated environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python -m ruff check src tests benchmarks examples
python -m build
```

On Windows use `.venv\Scripts\Activate.ps1`. The package has no runtime dependencies;
development tools are versioned in `pyproject.toml`. Run the README quickstart
after changing packaging or command-line behavior.

## Change expectations

- Add a small regression fixture for a demonstrated bug. Synthetic profiles and
  offers are enough; do not include participant records or private datasets.
- Preserve the frozen public reference in `tests/reference/negolog_v2_cbom.py`.
  If model semantics change intentionally, document the difference and extend
  the tests rather than silently changing the oracle.
- State whether a change affects utility estimates, strategy decisions, search
  approximation, public APIs or only execution cost.
- Keep source attributions, the GPL license, citation keys and paper metadata.
- Include run configuration and raw measurements with performance claims.
  Do not describe a synthetic software benchmark as a reproduced paper result.

The [method guide](docs/method.md) and [provenance record](docs/provenance.md)
define the current reference behavior and known differences from the paper.

## Report a bug

Provide the software version, interpreter version, operating system, a small
profile and offer sequence, expected behavior, observed behavior and settings.
If reporting search behavior, include `mode`, `sample_size`, `seed` and the
relevant trace row. Remove personal or confidential data before sharing.
