---
title: Tool reference - 13 read-only Yahoo Finance tools for AI agents
description: Every yfinance-agent-mcp tool at a glance - what it answers, Yahoo requests per call, cache time, and the fields every answer shares.
---

# Tool reference

yfinance-agent-mcp has 13 read-only tools. Together they cover what yfinance can fetch,
grouped by the questions an agent asks rather than by library method.

| Tool | Answers | Yahoo requests | Cached for |
|---|---|---|---|
| [`search_symbols`](search_symbols.md) | Which symbol is this company, fund or coin? | 1 | 2 min |
| [`get_quotes`](get_quotes.md) | Latest price, change, volume and freshness, up to 25 symbols | 1 per symbol (+3 with details) | 15 s |
| [`get_market_overview`](get_market_overview.md) | Is the market open; how are the indices doing? | 2 | 30 s |
| [`get_price_history`](get_price_history.md) | Trend, momentum, volatility; the latest bars | 1 per symbol | 30 s intraday, 5 min daily |
| [`get_news`](get_news.md) | Latest news for symbols or a topic | 1 per symbol, 1 per query | 2 min |
| [`screen_securities`](screen_securities.md) | Candidates from a predefined or custom screen | 1 | 1 min |
| [`get_sector_industry`](get_sector_industry.md) | Leaders, ETFs and industries of a sector or industry | 1 | 6 h |
| [`get_events`](get_events.md) | Earnings, IPO, economic and split calendars | 1, or 2 per symbol | 1 h |
| [`get_fundamentals`](get_fundamentals.md) | Statements, valuation history, key ratios | 1 to 3 | 6 h |
| [`get_analyst_view`](get_analyst_view.md) | Targets, ratings, estimates and revisions | about 6 | 1 h |
| [`get_options`](get_options.md) | Option chain around the price, all expirations | 2 | 1 min |
| [`get_ticker_dataset`](get_ticker_dataset.md) | Holders, insiders, dividends, filings, fund holdings... | 1 to 3 | 6 h |
| [`get_live_quotes`](get_live_quotes.md) | The price right now from the streaming feed | none (one shared websocket) | not cached |

Request counts are approximate. The first call in a process also fetches a Yahoo cookie
and crumb, and the first request for a new symbol may look up its timezone once. Cache
times are defaults; [configuration](../configuration.md) explains how to change them.

## What every answer contains

Every tool returns structured content (an output schema is declared) with these fields
next to its own data:

| Field | Meaning |
|---|---|
| `as_of` | When the data was fetched from Yahoo, UTC. Cached answers keep their original time. |
| `source` | `Yahoo Finance via yfinance <version>`. |
| `warnings` | Caveats: delayed quotes, symbols without data, trimmed results, how to get more. |
| `truncated` | `true` when rows were left out to keep the answer small. |
| `next_offset` | For paged results (`get_ticker_dataset`), the `offset` of the next page. |

Tools that take several symbols also return `errors`: one entry per symbol without data,
with a code and a message, so one bad symbol never fails the whole call.

## response_format

Every tool accepts `response_format`:

- `concise` (default): at most 20,000 characters, enough for most questions.
- `detailed`: at most 80,000 characters, for full statements or long tables.

Each tool caps its rows up front (for example 20 bars, 10 rating changes, 25 screen rows);
the budget is a last safety net that trims the longest list and says so in `warnings`.

## Errors

When a call cannot be answered, the tool returns an MCP error result whose text starts with
a code:

| Code | Meaning | What to do |
|---|---|---|
| `rate_limited` | Yahoo answered HTTP 429, or the server is pausing after one. | Wait the seconds given, then retry; batch symbols. |
| `not_found` | Unknown or delisted symbol, or no data for the range. | Check the symbol with `search_symbols`, or widen the range. |
| `invalid_argument` | The request cannot be answered as asked. | Use one of the valid values listed in the message. |
| `upstream_error` | Yahoo or the network failed. | Retry later; persistent errors may mean Yahoo changed its API. |

## Tool annotations

All tools are annotated `readOnlyHint: true` and `openWorldHint: true`: they only read
public market data. Clients may use that to approve them without asking every time.
