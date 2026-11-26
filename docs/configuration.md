---
title: Configuration - rate limits, cache times, locale and proxy
description: Every yfinance-agent-mcp setting - rate limit, burst, cache expiry, cache folder, Yahoo locale, proxy and log level - set by environment variables.
---

# Configuration

yfinance-agent-mcp works without configuration. Every setting is an environment variable,
set in your client's server entry (for example the `env` block of `mcp.json`) or in the
shell that starts the server. Invalid values stop the server at startup with a message that
names the variable.

| Variable | Default | Meaning |
|---|---|---|
| `YFINANCE_AGENT_MCP_RATE_LIMIT` | `2` | Requests per second to Yahoo, for the whole process. Must be above 0. |
| `YFINANCE_AGENT_MCP_RATE_BURST` | `5` | Requests allowed at once before pacing starts. Whole number, 1 or more. |
| `YFINANCE_AGENT_MCP_CACHE_DIR` | your user cache folder | Where yfinance keeps its timezone, cookie and ISIN caches (SQLite). |
| `YFINANCE_AGENT_MCP_LANG` | `en-US` | Yahoo locale language (BCP 47), e.g. `de-DE`. Affects names and news. |
| `YFINANCE_AGENT_MCP_REGION` | `US` | Yahoo locale region (ISO country code), e.g. `DE`. |
| `YFINANCE_AGENT_MCP_PROXY` | none | Proxy URL for all Yahoo requests, e.g. `http://proxy.local:8080`. |
| `YFINANCE_AGENT_MCP_LOG_LEVEL` | `WARNING` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. Logs go to stderr. The `--log-level` command-line option overrides it. |

The default cache folder is `~/.cache/yfinance-agent-mcp` on Linux,
`~/Library/Caches/yfinance-agent-mcp` on macOS and
`%LOCALAPPDATA%\yfinance-agent-mcp\Cache` on Windows.

## Cache expiry

Answers are cached in memory so repeated questions do not cost Yahoo requests. Each kind of
data has its own expiry, in seconds. Override one with
`YFINANCE_AGENT_MCP_TTL_<CATEGORY>=<seconds>`; `0` turns caching off for that category.

| Variable | Default | Used by |
|---|---|---|
| `YFINANCE_AGENT_MCP_TTL_QUOTES` | 15 | `get_quotes` |
| `YFINANCE_AGENT_MCP_TTL_HISTORY_INTRADAY` | 30 | `get_price_history` with intraday intervals |
| `YFINANCE_AGENT_MCP_TTL_HISTORY_DAILY` | 300 | `get_price_history` with daily or longer intervals |
| `YFINANCE_AGENT_MCP_TTL_NEWS` | 120 | `get_news` |
| `YFINANCE_AGENT_MCP_TTL_SEARCH` | 120 | `search_symbols` |
| `YFINANCE_AGENT_MCP_TTL_MARKET` | 30 | `get_market_overview` |
| `YFINANCE_AGENT_MCP_TTL_SCREEN` | 60 | `screen_securities` |
| `YFINANCE_AGENT_MCP_TTL_OPTIONS` | 60 | `get_options` |
| `YFINANCE_AGENT_MCP_TTL_EVENTS` | 3600 | `get_events` |
| `YFINANCE_AGENT_MCP_TTL_ANALYSTS` | 3600 | `get_analyst_view` |
| `YFINANCE_AGENT_MCP_TTL_FUNDAMENTALS` | 21600 | `get_fundamentals` |
| `YFINANCE_AGENT_MCP_TTL_DATASETS` | 21600 | `get_ticker_dataset` |
| `YFINANCE_AGENT_MCP_TTL_SECTOR` | 21600 | `get_sector_industry` |

An unknown category stops the server with the list of valid ones. Live prices
(`get_live_quotes`) are never cached: the stream keeps the latest tick.

## Examples

A slower, more cautious server that refreshes quotes every 5 seconds:

```json
{
  "mcpServers": {
    "yfinance": {
      "command": "uvx",
      "args": ["yfinance-agent-mcp"],
      "env": {
        "YFINANCE_AGENT_MCP_RATE_LIMIT": "1",
        "YFINANCE_AGENT_MCP_RATE_BURST": "2",
        "YFINANCE_AGENT_MCP_TTL_QUOTES": "5"
      }
    }
  }
}
```

German names and news for European symbols:

```bash
YFINANCE_AGENT_MCP_LANG=de-DE YFINANCE_AGENT_MCP_REGION=DE uvx yfinance-agent-mcp
```

See [rate limits and caching](guides/rate-limits-and-caching.md) for how the limits behave.
