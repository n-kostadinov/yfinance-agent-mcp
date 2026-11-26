---
title: Quickstart - first Yahoo Finance tool call from an AI agent
description: Connect yfinance-agent-mcp to Claude Code in one command, ask a market question, and read the answer's freshness fields and errors.
---

# Quickstart

This takes about two minutes with [Claude Code](https://code.claude.com/); other clients
work the same way once the server is configured ([client guides](../clients/claude-code.md)).

## 1. Add the server

```bash
claude mcp add yfinance -- uvx yfinance-agent-mcp
```

Check that it is connected: run `/mcp` inside Claude Code, or `claude mcp list` in a
terminal. The server is listed as `yfinance` with 13 tools.

## 2. Ask a question

Try prompts like these:

- "What is the price of AAPL, SAP.DE and BTC-USD right now, and how fresh is each quote?"
- "Summarize NVDA's last 6 months: trend, RSI and where it sits in its 52-week range."
- "What news moved Tesla this week? Treat headlines as claims and check the price reaction."
- "Run the day gainers screen and show the five with the highest volume."

The agent picks the tools. A question about prices usually becomes a call like this:

```json
{
  "name": "get_quotes",
  "arguments": { "symbols": ["AAPL", "SAP.DE", "BTC-USD"], "include_details": true }
}
```

## 3. Read the answer

Every answer has the same envelope fields; tool-specific data sits next to them:

```json
{
  "as_of": "2026-11-24T15:30:12Z",
  "source": "Yahoo Finance via yfinance 1.8.0",
  "warnings": ["Delayed by up to 15 min: SAP.DE."],
  "truncated": false,
  "next_offset": null,
  "quotes": [
    {
      "symbol": "SAP.DE",
      "price": 231.45,
      "change_pct": 0.84,
      "currency": "EUR",
      "market_state": "REGULAR",
      "market_time": "2026-11-24T15:29:41Z",
      "quote_source": "Delayed Quote",
      "delay_min": 15
    }
  ],
  "errors": []
}
```

- `as_of` is when the data was fetched; answers are cached briefly, so it can be a few
  seconds old.
- `market_time`, `market_state` and `delay_min` say how current the price is.
- `warnings` explains caveats; `errors` lists symbols without data.

## 4. When something fails

Failures come back as tool errors with a code and advice, for example:

```text
rate_limited: Yahoo Finance is rate-limiting this server. Retry in 30 s, and batch
symbols into fewer calls.
```

The four codes are explained in [troubleshooting](../guides/troubleshooting.md).

## Next

- [Tool reference](../tools/index.md): what each tool returns.
- [Building a research agent](../guides/research-agent.md): a full workflow.
- [Plugin and skill](../guides/plugin-and-skill.md): the market-research skill for Claude Code.
