---
title: Use the yfinance MCP server in Claude Desktop
description: Configure Claude Desktop to start yfinance-agent-mcp with uvx through claude_desktop_config.json on macOS and Windows, with environment variables.
---

# Claude Desktop

## Configure

Open **Settings → Developer → Edit Config**, or edit the file directly:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add the server under `mcpServers`:

```json
{
  "mcpServers": {
    "yfinance": {
      "command": "uvx",
      "args": ["yfinance-agent-mcp"],
      "env": {
        "YFINANCE_AGENT_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

The `env` block is optional; [configuration](../configuration.md) lists every setting.
Restart Claude Desktop.

## Verify

Open a new chat and look for the tools icon: `yfinance` should be listed with 13 tools.
Ask: "What are today's day gainers in the US?"

## uvx not found

Claude Desktop does not read your shell profile, so `uvx` may not be on its `PATH`. Use the
full path instead:

=== "macOS"

    ```bash
    which uvx
    ```

    then set `"command"` to the result, for example `"/Users/you/.local/bin/uvx"`.

=== "Windows"

    ```powershell
    where.exe uvx
    ```

    then set `"command"` to the result, for example
    `"C:\\Users\\you\\.local\\bin\\uvx.exe"` (double the backslashes in JSON).

## Logs

Claude Desktop writes each server's stderr to a log file:

- macOS: `~/Library/Logs/Claude/mcp-server-yfinance.log`
- Windows: `%APPDATA%\Claude\logs\mcp-server-yfinance.log`

Set `YFINANCE_AGENT_MCP_LOG_LEVEL` to `DEBUG` to see every Yahoo request.
