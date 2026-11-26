from __future__ import annotations

import pytest
from mcp import Client

from tests.fakes import FakeGateway

pytestmark = pytest.mark.anyio


async def test_get_live_quotes_returns_streamed_ticks(
    client: Client, fake_gateway: FakeGateway
) -> None:
    fake_gateway.live_ticks["BTC-USD"] = {"id": "BTC-USD", "price": 87_000.5}

    result = await client.call_tool(
        "get_live_quotes", {"symbols": ["BTC-USD", "AAPL"], "wait_seconds": 0.2}
    )

    assert result.structured_content is not None
    assert result.structured_content["ticks"][0]["price"] == 87_000.5
    assert result.structured_content["missing"] == ["AAPL"]
