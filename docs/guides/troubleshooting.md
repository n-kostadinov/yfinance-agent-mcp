---
title: Troubleshooting the yfinance MCP server - errors and fixes
description: Fix common yfinance-agent-mcp problems - uvx not found, server not starting, rate_limited, not_found, invalid_argument, upstream_error and empty live prices.
---

# Troubleshooting

## The server does not start

1. Run the server by hand:

    ```bash
    uvx yfinance-agent-mcp --version
    ```

    If this fails, the client cannot start it either.

2. **`uvx` not found:** install [uv](../getting-started/installation.md). Desktop apps do not
   read your shell profile, so use the full path to `uvx` in the client configuration
   (`which uvx`, or `where.exe uvx` on Windows).
3. **A configuration error** names the variable, for example
   `yfinance-agent-mcp: YFINANCE_AGENT_MCP_RATE_LIMIT must be a number, got 'fast'`. Fix the
   value in the client's `env` block ([configuration](../configuration.md)).
4. **Cache folder not writable:** set `YFINANCE_AGENT_MCP_CACHE_DIR` to a writable folder.

To see what the server does, set `YFINANCE_AGENT_MCP_LOG_LEVEL=DEBUG`; logs go to stderr,
which most clients write to a log file.

## Error codes

### rate_limited

```text
rate_limited: Yahoo Finance is rate-limiting this server. Retry in 30 s, and batch symbols into fewer calls.
```

Yahoo answered HTTP 429, or the server is pausing after one. Wait the given time. If it
keeps happening, lower `YFINANCE_AGENT_MCP_RATE_LIMIT`, batch symbols, and check that no
other program on the same IP address is hammering Yahoo. See
[rate limits and caching](rate-limits-and-caching.md).

### not_found

```text
not_found: $XYZ: possibly delisted; no price data found (period=5d)
```

The symbol is unknown, delisted, or has no data for the range. Check it with
`search_symbols`; non-US listings need a suffix (`SAP.DE`, `7203.T`, `VOD.L`). Fund datasets
of `get_ticker_dataset` exist only for ETFs and funds.

### invalid_argument

```text
invalid_argument: 5m bars only cover the last 60 days; use interval 1d for more. Valid values: 1d, 5d, 1mo.
```

The request cannot be answered as asked; the message lists what would work.

### upstream_error

```text
upstream_error: network error talking to Yahoo Finance: ... Retry later; if this keeps happening, Yahoo may have changed its API (check for a yfinance-agent-mcp update).
```

Yahoo or the network failed. Retry later. If it persists for every call, Yahoo may have
changed an endpoint: upgrade with `uvx yfinance-agent-mcp@latest`, and check the
[issues](https://github.com/n-kostadinov/yfinance-agent-mcp/issues).

## Other problems

- **`get_live_quotes` lists every symbol in `missing`:** the market is closed or the symbols
  are illiquid; crypto (`BTC-USD`) streams around the clock. Your network must allow the
  websocket to `streamer.finance.yahoo.com`.
- **News is empty:** Yahoo has news only for some locales; try `YFINANCE_AGENT_MCP_REGION=US`.
- **A result says `truncated: true`:** ask for fewer symbols or rows, or use
  `response_format: "detailed"`.
- **Behind a corporate proxy:** set `YFINANCE_AGENT_MCP_PROXY`.

Still stuck? Open an [issue](https://github.com/n-kostadinov/yfinance-agent-mcp/issues/new/choose)
with the version, the client, the tool call and the debug log.
