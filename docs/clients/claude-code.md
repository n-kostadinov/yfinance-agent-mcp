---
title: Use the yfinance MCP server in Claude Code
description: Add yfinance-agent-mcp to Claude Code with one command or install the plugin with its market-research skill; set environment variables and verify it.
---

# Claude Code

## Add the server

```bash
claude mcp add yfinance -- uvx yfinance-agent-mcp
```

Options you may want:

- `--scope user` makes the server available in every project; `--scope project` writes it
  to the project's `.mcp.json` so your team gets it too.
- `-e NAME=value` sets an environment variable, for example
  `-e YFINANCE_AGENT_MCP_RATE_LIMIT=1` ([all settings](../configuration.md)).
- Pin a version with `uvx yfinance-agent-mcp@0.1.0`.

```bash
claude mcp add yfinance --scope user -e YFINANCE_AGENT_MCP_LOG_LEVEL=INFO -- uvx yfinance-agent-mcp@0.1.0
```

## Or install the plugin

The plugin adds the same server plus a market-research skill that walks the agent from
news to a decision record:

```text
/plugin marketplace add n-kostadinov/yfinance-agent-mcp
/plugin install yfinance@yfinance-agent-mcp
```

On Claude Code 2.1.275 or later, one step is enough:
`/plugin install yfinance --marketplace n-kostadinov/yfinance-agent-mcp`.
The skill runs as `/yfinance:market-research`. See [plugin and skill](../guides/plugin-and-skill.md).

## Verify

- Inside Claude Code, run `/mcp`: `yfinance` should be connected with 13 tools.
- In a terminal, `claude mcp list` shows its status.
- Ask: "Is the US market open right now?" The agent should call `get_market_overview`.

## Tool names and permissions

Claude Code names the tools `mcp__yfinance__<tool>`, for example
`mcp__yfinance__get_quotes` (with the plugin: `mcp__plugin_yfinance_yfinance__get_quotes`).
All tools are read-only and annotated as such, so you can pre-approve them, for example in
`.claude/settings.json`:

```json
{
  "permissions": {
    "allow": ["mcp__yfinance__*"]
  }
}
```

## Troubleshooting

- **`uvx` not found:** Claude Code inherits your shell's `PATH`. Install
  [uv](../getting-started/installation.md) and restart the terminal, or use the full path
  from `which uvx` (`where uvx` on Windows).
- **The server shows as failed:** run `uvx yfinance-agent-mcp --version` in a terminal to see
  the error. More in [troubleshooting](../guides/troubleshooting.md).
