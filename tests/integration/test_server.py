from __future__ import annotations

import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from yfinance_agent_mcp import __version__
from yfinance_agent_mcp.server import SERVER_NAME

pytestmark = pytest.mark.anyio


async def test_in_process_client_lists_the_server_tools(client: Client) -> None:
    tools = await client.list_tools()

    assert all(tool.annotations and tool.annotations.read_only_hint for tool in tools.tools)


async def test_server_speaks_mcp_over_stdio_with_a_clean_stdout(tmp_path: Path) -> None:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "yfinance_agent_mcp"],
        env={"YFINANCE_AGENT_MCP_CACHE_DIR": str(tmp_path)},
    )

    async with Client(server, mode="legacy", read_timeout_seconds=60) as client:
        await client.list_tools()
        server_info = client.server_info

    assert server_info is not None
    assert (server_info.name, server_info.version) == (SERVER_NAME, __version__)
