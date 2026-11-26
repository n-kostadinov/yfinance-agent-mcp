---
title: Use the yfinance MCP server in VS Code with Copilot
description: Add yfinance-agent-mcp to VS Code through .vscode/mcp.json and use its Yahoo Finance tools from GitHub Copilot's agent mode.
---

# VS Code

VS Code runs MCP servers for GitHub Copilot's agent mode.

## Configure

Create `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "yfinance": {
      "type": "stdio",
      "command": "uvx",
      "args": ["yfinance-agent-mcp"],
      "env": {
        "YFINANCE_AGENT_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Note the top-level key is `servers`, not `mcpServers`. To use the server in every workspace,
run **MCP: Open User Configuration** from the Command Palette and add the same entry there.

## Verify

- Run **MCP: List Servers** from the Command Palette; `yfinance` should be running.
- Open Copilot Chat, switch to **Agent** mode, and open the tools picker: the 13 yfinance
  tools are listed and can be toggled.
- Ask: "What is the market doing today?"

## Troubleshooting

**MCP: List Servers → yfinance → Show Output** shows the server's log. If it cannot start,
run `uvx yfinance-agent-mcp --version` in a terminal. More in
[troubleshooting](../guides/troubleshooting.md).
