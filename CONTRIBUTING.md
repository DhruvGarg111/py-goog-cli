# Contributing

## Development setup

```bash
git clone https://github.com/DhruvGarg111/py-goog-cli.git
cd py-goog-cli
uv sync --all-groups --extra agent
```

Run the focused suite or the complete suite:

```bash
uv run pytest -q
uv run pytest tests/services tests/auth tests/commands -q
```

Quality commands used by CI:

```bash
uv run ruff check pygog tests
uv run ruff format --check pygog tests
uv run mypy pygog
uv run bandit --recursive pygog --severity-level medium
uv run pip-audit
uv build
```

The repository currently has known legacy Ruff and mypy debt; do not hide new
findings behind broad suppressions. Keep behavior changes and mechanical
formatting in separate changes where possible.

## Pull requests

- Add a regression test for behavior changes.
- Keep credentials, tokens, and generated build artifacts out of commits.
- Explain compatibility impacts for JSON/TSV output or CLI flags.
- Do not commit, push, or release artifacts without the maintainer's approval.
