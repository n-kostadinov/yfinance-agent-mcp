---
title: Rate limits and caching - staying friendly with Yahoo Finance
description: How yfinance-agent-mcp paces Yahoo requests, pauses after HTTP 429, caches answers per category, and what an agent should do when it is rate limited.
---

# Rate limits and caching

Yahoo Finance throttles clients by IP address. Too many requests in a short time return
HTTP 429, and a persistent block can last hours. The server is built to avoid that.

## How requests are paced

- **One session.** Every tool shares one Yahoo session (one cookie and crumb) for the life of
  the process, instead of a new handshake per call.
- **A process-wide rate limit.** Every HTTP request, including the cookie and crumb
  requests, passes through one token bucket: by default bursts of 5, then 2 per second.
  Calls wait their turn rather than fail.
- **A pause after HTTP 429.** When Yahoo answers 429, every request stops for 30 seconds.
  Another 429 right after doubles the pause, up to 5 minutes; a successful request resets
  it. During a pause, tools answer at once with `rate_limited` and the seconds to wait.
- **Multi-symbol calls stop early.** After a rate limit, `get_quotes`, `get_price_history`,
  `get_news` and `get_events` report the remaining symbols in `errors` as `rate_limited`
  instead of requesting them.

Tune the pace with `YFINANCE_AGENT_MCP_RATE_LIMIT` and `YFINANCE_AGENT_MCP_RATE_BURST`
([configuration](../configuration.md)).

## How answers are cached

Each answer is cached by tool and arguments for a time that suits the data: 15 seconds for
quotes, 2 minutes for news, 6 hours for fundamentals ([full table](../configuration.md#cache-expiry)).
A cached answer keeps the `as_of` of its original fetch, so the agent can always see its age.
Failures are never cached.

yfinance itself caches some responses for the life of the process with no expiry; the server
clears that cache before each request so its own expiry times decide freshness.

## What an agent should do

1. **Batch.** One `get_quotes` call with 20 symbols is far cheaper than 20 calls.
2. **Prefer summaries.** `get_price_history` in summary mode gives indicators without
   requesting more bars.
3. **On `rate_limited`, wait** the number of seconds in the message, then retry once.
4. **Don't poll in a tight loop.** Asking for the same quote every second only returns the
   cached answer; use `get_live_quotes` for continuous prices.

## Request costs

The [tool reference](../tools/index.md) lists approximate Yahoo requests per call. The
first call in a process also fetches a cookie and crumb, and the first request for a symbol
may look up its timezone, which is then cached on disk.
