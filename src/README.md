# Python Source

The installable implementation lives in [`ojcoms_poc/`](ojcoms_poc/README.md). The repository uses the standard `src` layout so tests import the installed package rather than accidentally importing files from the project root.

Install it in editable mode after the pinned dependencies:

```bash
python -m pip install -r requirements/base.lock
python -m pip install --no-deps -e .
```

The command-line entry point declared in `pyproject.toml` is `agentic-edge-poc`.
