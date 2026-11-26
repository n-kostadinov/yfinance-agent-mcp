from __future__ import annotations

import pytest
from mcp import Client

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_quarterly_income_and_key_stats(live_client: Client) -> None:
    income = await live_client.call_tool(
        "get_fundamentals", {"symbol": "AAPL", "statement": "income", "freq": "quarterly"}
    )
    stats = await live_client.call_tool(
        "get_fundamentals", {"symbol": "AAPL", "statement": "key_stats"}
    )

    assert income.structured_content is not None
    assert stats.structured_content is not None
    assert income.structured_content["periods"][0]["total_revenue"] > 0
    assert stats.structured_content["key_stats"]["market_cap"] > 0


async def test_valuation_measures(live_client: Client) -> None:
    result = await live_client.call_tool(
        "get_fundamentals", {"symbol": "MSFT", "statement": "valuation"}
    )

    assert result.structured_content is not None
    assert result.structured_content["periods"][0]["period"] == "Current"


async def test_analyst_view(live_client: Client) -> None:
    result = await live_client.call_tool("get_analyst_view", {"symbol": "AAPL"})

    assert result.structured_content is not None
    content = result.structured_content
    assert content["price_targets"]["mean"] > 0
    assert 0 < len(content["rating_changes"]) <= 10
    assert len(content["earnings_estimate"]) > 0
