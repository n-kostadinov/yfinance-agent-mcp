# Contributing to yfinance-agent-mcp

Thanks for helping. This guide gets you from a fresh clone to a passing test run.

## Set up

You need [uv](https://docs.astral.sh/uv/) 0.13.9 or newer (`uv self update`). The project
pins that minimum in `pyproject.toml`, so an older uv stops with a clear message.

```bash
git clone https://github.com/n-kostadinov/yfinance-agent-mcp.git
cd yfinance-agent-mcp
uv sync
uv run yfinance-agent-mcp --version
```

## Check your change

```bash
uv run ruff format .
uv run ruff check .
uv run pyright
uv run pytest --cov            # offline tests; fails below 85% coverage
uv run pytest -m live          # calls Yahoo Finance; run before touching gateway.py
uv run python scripts/set_version.py --check
```

- **Unit tests** (`tests/unit`) cover logic with the in-memory `FakeGateway`.
- **Integration tests** (`tests/integration`) run the real MCP server in-process, the stdio
  entry point, and the yfinance gateway against a fake HTTP layer. No network.
- **Live tests** (`tests/live`, marker `live`) use the real gateway against Yahoo. They run
  nightly in CI and are not part of the default run.

Only `src/yfinance_agent_mcp/gateway.py` may import yfinance; a test enforces it.

## Documentation

The site is built with [Zensical](https://zensical.org/) from `docs/`:

```bash
uv run zensical serve          # preview on http://localhost:8000
uv run zensical build --clean
uv run python scripts/check_seo.py site
```

When you add or change a tool parameter, update its page under `docs/tools/`; a drift test
fails otherwise.

## Pull requests

- Keep each pull request to one change, with tests that fail without it.
- Add a line under `## [Unreleased]` in `CHANGELOG.md`.
- Describe how you verified the change.

Releases are made by the maintainer; see
[Releasing](https://n-kostadinov.github.io/yfinance-agent-mcp/development/releasing/).
