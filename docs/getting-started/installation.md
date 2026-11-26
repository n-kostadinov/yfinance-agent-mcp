---
title: Install the yfinance MCP server with uv and uvx
description: Install yfinance-agent-mcp with uvx in one command, pin a version, upgrade, or install it as a tool. Python and dependencies are handled by uv.
---

# Installation

yfinance-agent-mcp is a Python package on [PyPI](https://pypi.org/project/yfinance-agent-mcp/).
The simplest way to run it is `uvx`, which downloads the package into a cached environment
and starts it. MCP clients start the server themselves; you only tell them the command.

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/), which provides `uvx`.
  uv also downloads a suitable Python (3.11 or newer) if your system has none.
- Network access to Yahoo Finance (`*.finance.yahoo.com`, `fc.yahoo.com` and the
  `streamer.finance.yahoo.com` websocket for live prices).

Install uv if you do not have it:

=== "macOS and Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

## Check that it runs

```bash
uvx yfinance-agent-mcp --version
```

This prints `yfinance-agent-mcp` and the version. Without `--version` the server waits for
an MCP client on stdin and stdout; stop it with ++ctrl+c++. Nothing else is printed on
stdout, because stdout carries the protocol; logs go to stderr.

## Pin a version

Clients run whatever `uvx` resolves. To get the same server every time, pin it:

```bash
uvx yfinance-agent-mcp@0.1.0
```

In a client configuration, put the pinned form into `args`:

```json
{ "command": "uvx", "args": ["yfinance-agent-mcp@0.1.0"] }
```

## Upgrade

`uvx` caches the environment it built. Ask for the latest release explicitly:

```bash
uvx yfinance-agent-mcp@latest --version
```

and use `yfinance-agent-mcp@latest` in your client configuration, or bump your pinned
version. The [changelog](../changelog.md) lists what changed.

## Other ways to install

=== "uv tool"

    Installs a persistent `yfinance-agent-mcp` command:

    ```bash
    uv tool install yfinance-agent-mcp
    yfinance-agent-mcp --version
    ```

    Configure clients with `"command": "yfinance-agent-mcp"` and no arguments.

=== "pip"

    ```bash
    python -m venv .venv
    .venv/bin/pip install yfinance-agent-mcp     # Windows: .venv\Scripts\pip
    .venv/bin/yfinance-agent-mcp --version
    ```

    Configure clients with the full path to `.venv/bin/yfinance-agent-mcp`.

=== "Claude Code plugin"

    The plugin starts the server with `uvx` and adds a market-research skill:

    ```text
    /plugin marketplace add n-kostadinov/yfinance-agent-mcp
    /plugin install yfinance@yfinance-agent-mcp
    ```

    See [the plugin and skill](../guides/plugin-and-skill.md).

## Try it without a chat client

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) lists the tools and
lets you call them from a browser:

```bash
npx @modelcontextprotocol/inspector uvx yfinance-agent-mcp
```

## Next

- [Quickstart](quickstart.md): connect a client and make a first call.
- [Configuration](../configuration.md): rate limits, cache times, locale and proxy.
