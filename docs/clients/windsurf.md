---
title: Use the yfinance MCP server in Windsurf
description: Add yfinance-agent-mcp to Windsurf's Cascade through mcp_config.json, refresh the server list, and call its Yahoo Finance tools.
---

# Windsurf

## Configure

Open **Windsurf Settings → Cascade → MCP Servers → View raw config**, or edit
`~/.codeium/windsurf/mcp_config.json` directly:

```json
{
  "mcpServers": {
    "yfinance": {
      "command": "uvx",
      "args": ["yfinance-agent-mcp"]
    }
  }
}
```

Add an `env` object for [settings](../configuration.md) if needed.

## Verify

Refresh the MCP server list in Cascade; `yfinance` should show 13 tools. Ask Cascade
"How did Bitcoin trade over the last 5 days?"

## Troubleshooting

If the server does not start, check that `uvx yfinance-agent-mcp --version` works in a
terminal, and use the full path to `uvx` in `"command"`. See
[troubleshooting](../guides/troubleshooting.md).
