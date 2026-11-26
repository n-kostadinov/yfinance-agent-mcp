"""In-process MCP client fixtures: the real server wired to the fake gateway."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from mcp import Client

from tests.fakes import FakeGateway
from yfinance_agent_mcp.config import Settings
from yfinance_agent_mcp.server import create_server


@pytest.fixture
def fake_gateway() -> FakeGateway:
    return FakeGateway()


@pytest.fixture(params=["auto", "legacy"])
async def client(
    request: pytest.FixtureRequest, fake_gateway: FakeGateway, tmp_path: Path
) -> AsyncIterator[Client]:
    """A connected client, once per protocol mode: 2026-era dispatch and the legacy handshake."""
    server = create_server(Settings(cache_dir=tmp_path), gateway=fake_gateway)
    async with Client(server, mode=request.param, raise_exceptions=True) as connected:
        yield connected
