"""MCP tools, one module per capability group; ``register_tools`` adds them all to a server."""

from __future__ import annotations

from mcp.server import MCPServer

from yfinance_agent_mcp.tools import (
    datasets,
    events,
    fundamentals,
    markets,
    news,
    options,
    prices,
    screening,
    streaming,
)
from yfinance_agent_mcp.tools.context import ToolContext


def register_tools(server: MCPServer, context: ToolContext) -> None:
    for register in (
        markets.register,
        prices.register,
        news.register,
        screening.register,
        events.register,
        fundamentals.register,
        options.register,
        datasets.register,
        streaming.register,
    ):
        register(server, context)
