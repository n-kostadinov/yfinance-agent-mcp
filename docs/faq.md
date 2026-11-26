---
title: FAQ - yfinance MCP server for AI agents
description: Answers about yfinance-agent-mcp - cost, real-time data, trading, markets covered, API keys, transports, commercial use and how it differs from yfinance.
---

# Frequently asked questions

## Is it free?

Yes. The server is open source under the MIT license and needs no API key. Yahoo Finance's
data is offered for personal use; see the [disclaimer](disclaimer.md).

## Is the data real-time?

Sometimes. Yahoo shows real-time prices for some markets (for example US stocks through
Nasdaq, and crypto) and delays others, typically by 15 minutes. Every quote says how fresh
it is; see [data freshness](guides/data-freshness.md). For the price right now, use
[`get_live_quotes`](tools/get_live_quotes.md).

## Can it place trades?

No. Every tool is read-only. An agent that trades needs a separate, gated tool from your
broker; keeping that separate is deliberate ([research agent guide](guides/research-agent.md)).

## Which markets does it cover?

Whatever Yahoo Finance covers: stocks and ETFs on most exchanges (use Yahoo's suffixes such
as `SAP.DE`, `VOD.L`, `7203.T`), indices (`^GSPC`), currencies (`EURUSD=X`), futures
(`ES=F`), crypto (`BTC-USD`) and mutual funds.

## Do I need an API key or a Yahoo account?

No. The server uses Yahoo Finance's public endpoints through yfinance.

## Why `yfinance-agent-mcp` and not `yfinance-mcp`?

The name `yfinance-mcp` on PyPI belongs to an unrelated project. This server's name
emphasizes what it is built for: agents.

## How is it different from calling yfinance directly?

yfinance returns pandas objects and is built for scripts. This server returns small,
documented JSON answers with indicators, freshness fields and actionable errors; it paces
requests, caches answers, and keeps yfinance's process-wide state safe for a long-running
agent. See [architecture](architecture.md).

## Why stdio only?

Every common MCP client starts local servers over stdio, and stdio opens no network port, so
there is nothing to secure. An HTTP transport may come later.

## Can I use it commercially?

The code is MIT licensed, but Yahoo's terms say the data is for personal use. For a
commercial product, use a licensed market data provider.

## Does it work on Windows, macOS and Linux?

Yes; CI tests all three with Python 3.11 to 3.14.

## Where do I report a bug?

In the [issue tracker](https://github.com/n-kostadinov/yfinance-agent-mcp/issues/new/choose).
Report security problems privately; see the
[security policy](https://github.com/n-kostadinov/yfinance-agent-mcp/blob/main/SECURITY.md).
