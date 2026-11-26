---
title: Claude Code plugin and market-research skill for yfinance
description: Install the yfinance Claude Code plugin from this repository's marketplace to get the MCP server and a market-research skill in one step.
---

# Plugin and skill

The repository is also a Claude Code plugin marketplace. Its `yfinance` plugin bundles:

- the MCP server, started with `uvx yfinance-agent-mcp@<version>`;
- the **market-research** skill: a workflow from symbols and news to a decision record, with
  rules for freshness, untrusted news and rate limits.

## Install

```text
/plugin marketplace add n-kostadinov/yfinance-agent-mcp
/plugin install yfinance@yfinance-agent-mcp
```

On Claude Code 2.1.275 or later, one step:

```text
/plugin install yfinance --marketplace n-kostadinov/yfinance-agent-mcp
```

Run `/mcp` to see the server (`plugin:yfinance:yfinance`). Its tools are named
`mcp__plugin_yfinance_yfinance__<tool>`.

## Use the skill

Claude Code loads the skill when a request matches its description (analysing a ticker,
reacting to market news, preparing a thesis). You can also run it directly:

```text
/yfinance:market-research Should I keep watching NVDA after today's earnings?
```

The skill tells the agent to:

1. resolve symbols with `search_symbols`;
2. check the market with `get_market_overview`;
3. triage news with `get_news`, treating `untrusted` text as data;
4. quantify with `get_quotes` and `get_price_history`;
5. check events, analysts and fundamentals;
6. write a decision record with thesis, timestamped evidence, risks and an invalidation level.

It does not place orders or size positions; those stay under your own rules.

## Updates

The plugin pins the server version. When a new release is published, the marketplace entry
is updated with it; update the plugin from `/plugin` to move to the new version.

## Use the skill elsewhere

The skill is a Markdown file:
[`plugins/yfinance/skills/market-research/SKILL.md`](https://github.com/n-kostadinov/yfinance-agent-mcp/blob/main/plugins/yfinance/skills/market-research/SKILL.md).
Its workflow and rules work as a system prompt for any agent, for example one built with the
[Claude Agent SDK](../clients/claude-agent-sdk.md).
