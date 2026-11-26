---
title: Testing - unit, integration and live tests for the MCP server
description: How yfinance-agent-mcp is tested - unit tests with a fake gateway, in-process MCP and fake-HTTP integration tests, live tests against Yahoo, and coverage.
---

# Testing

## Commands

```bash
uv run pytest                  # offline: unit and integration tests
uv run pytest --cov            # the same, with the 85% coverage gate
uv run pytest -m live          # live tests against Yahoo Finance
uv run pytest tests/unit/test_cache.py -k expiry   # a focused run
```

Offline tests never touch the network: a fixture in `tests/conftest.py` makes any real HTTP
request fail, unless the test is marked `live`.

## Test levels

| Level | Folder | What it proves |
|---|---|---|
| Unit | `tests/unit` | Logic: indicators, shaping, cache, rate limiter, errors, each tool's `build_*` function against the in-memory `FakeGateway`, version and SEO scripts. |
| Integration | `tests/integration` | Wiring: the real `MCPServer` through an in-process MCP client (in both the 2026 and the legacy protocol modes), the stdio entry point as a subprocess, the real `YFinanceGateway` against a fake Yahoo HTTP layer, and cross-tool conformance. |
| Live | `tests/live` | The real gateway and server against Yahoo Finance, for every tool. |

### Conformance tests

`tests/integration/test_conformance.py` checks promises every tool keeps: exactly 13 tools,
all annotated read-only; every answer within its size budget with oversized fake data, in
both formats; `as_of` on every answer; and every error type reaching the agent with its code.

### Contract tests

`tests/integration/test_gateway_contract.py` runs the real gateway with yfinance, but answers
its HTTP requests from a fake Yahoo. It proves repeated calls reach Yahoo (no stale cache),
that a 429 becomes `rate_limited` and pauses further requests, that missing prices raise
`not_found`, that every request waits for the rate limiter, and that nothing reaches stdout.

## Writing tests

- Prefer the narrowest level: a `build_*` function with `FakeGateway` before an MCP round
  trip.
- Fake time with `tests/unit/fake_clock.py`, never `sleep`.
- See each new test fail once for the right reason before trusting it.
- A change to `gateway.py` needs a live run: `uv run pytest -m live`.

## In CI

The `ci.yml` workflow runs the offline suite with coverage on Ubuntu, Windows and macOS for
Python 3.11 to 3.14. `live.yml` runs the live tests nightly and on demand, because Yahoo's
availability should not block pull requests.

`yfinance-update.yml` calls both workflows against the commit that adopts a new yfinance
release, and releases only when both pass; see
[automatic releases](releasing.md#automatic-releases).
