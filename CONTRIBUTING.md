# Contributing

Thanks for helping improve NoteGPT Harvester!

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Before opening a PR

```bash
ruff check .
pytest
```

Both must pass. Keep the public behaviour stable and document any new config keys
in `config.example.toml` and the READMEs.

## Adding an email provider

1. Subclass `BaseEmailClient` in `src/notegpt_harvester/email_provider.py`.
2. Implement `start`, `close`, `create_address`, `fetch_messages`.
3. Register it in `TempEmailClient.create`.
4. Add a test (see `tests/test_e2e.py` for the stub pattern).

## Style

- Python 3.10+, type hints, `ruff` line length 120.
- No comments that restate code; explain *why* when non-obvious.
- Never commit `config.toml`, `results/`, or `harvest.state.json`.
