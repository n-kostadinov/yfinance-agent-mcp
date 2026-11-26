from __future__ import annotations

import pytest
from mcp import Client
from mcp.types import TextContent

from tests.fakes import FakeGateway, make_history

pytestmark = pytest.mark.anyio


async def test_price_history_returns_summary_and_bars(
    client: Client, fake_gateway: FakeGateway
) -> None:
    fake_gateway.histories["AAPL"] = make_history("AAPL", [100.0 + day for day in range(30)])

    result = await client.call_tool("get_price_history", {"symbols": ["AAPL"], "period": "1mo"})

    assert result.structured_content is not None
    prices = result.structured_content["prices"][0]
    assert prices["summary"]["rsi_14"] == 100.0
    assert len(prices["bars"]) == 20


async def test_impossible_range_is_an_actionable_tool_error(client: Client) -> None:
    result = await client.call_tool(
        "get_price_history", {"symbols": ["AAPL"], "period": "1y", "interval": "5m"}
    )

    assert result.is_error is True
    text = result.content[0]
    assert isinstance(text, TextContent)
    assert "invalid_argument: 5m bars only cover the last 60 days" in text.text
