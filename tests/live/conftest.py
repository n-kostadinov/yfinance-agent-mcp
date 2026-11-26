"""Live tests: the real server and gateway against Yahoo Finance (network, opt-in)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from mcp import Client

from yfinance_agent_mcp.config import Settings
from yfinance_agent_mcp.server import create_server


@pytest.fixture
async def live_client(tmp_path: Path) -> AsyncIterator[Client]:
    server = create_server(Settings(cache_dir=tmp_path))
    async with Client(server, raise_exceptions=True) as connected:
        yield connected
