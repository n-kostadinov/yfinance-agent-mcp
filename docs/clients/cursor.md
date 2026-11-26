---
title: Use the yfinance MCP server in Cursor
description: Add yfinance-agent-mcp to Cursor with a project or global mcp.json, check it in Cursor's MCP settings, and use its tools from the agent.
---

# Cursor

## Configure

Create `.cursor/mcp.json` in your project, or `~/.cursor/mcp.json` to use the server in
every project:

```json
{
  "mcpServers": {
    "yfinance": {
      "command": "uvx",
      "args": ["yfinance-agent-mcp"],
      "env": {
        "YFINANCE_AGENT_MCP_RATE_LIMIT": "2"
      }
    }
  }
}
```

The `env` block is optional ([configuration](../configuration.md)).

## Verify

Open **Cursor Settings → MCP**. `yfinance` should appear with a green status and 13 tools.
In the agent chat, ask "Compare AAPL and MSFT on valuation and 6-month trend"; Cursor asks
before running each tool unless you allow it.

## Troubleshooting

- A red status usually means `uvx` was not found or failed. Run
  `uvx yfinance-agent-mcp --version` in a terminal, and use the full path to `uvx` in
  `"command"` if needed.
- See [troubleshooting](../guides/troubleshooting.md) for tool errors.
