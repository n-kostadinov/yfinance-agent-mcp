from __future__ import annotations

import pytest
from mcp import Client

pytestmark = [pytest.mark.live, pytest.mark.anyio]

MARKET_STATES = {"PRE", "PREPRE", "REGULAR", "POST", "POSTPOST", "CLOSED"}


async def test_search_finds_nvidia(live_client: Client) -> None:
    result = await live_client.call_tool("search_symbols", {"query": "nvidia"})

    assert result.structured_content is not None
    assert "NVDA" in [match["symbol"] for match in result.structured_content["matches"]]


async def test_quotes_carry_prices_and_freshness_for_three_markets(live_client: Client) -> None:
    result = await live_client.call_tool(
        "get_quotes", {"symbols": ["AAPL", "SAP.DE", "BTC-USD"], "include_details": True}
    )

    assert result.structured_content is not None
    quotes = {q["symbol"]: q for q in result.structured_content["quotes"]}
    assert set(quotes) == {"AAPL", "SAP.DE", "BTC-USD"}
    for quote in quotes.values():
        assert quote["price"] > 0
        assert quote["market_state"] in MARKET_STATES
        assert quote["market_time"].endswith("Z")
        assert quote["delay_min"] is not None
    assert quotes["SAP.DE"]["currency"] == "EUR"
    assert quotes["BTC-USD"]["delay_min"] == 0


async def test_us_market_overview_has_status_and_indices(live_client: Client) -> None:
    result = await live_client.call_tool("get_market_overview", {"region": "US"})

    assert result.structured_content is not None
    assert result.structured_content["status"]["state"] in {"open", "closed"}
    assert len(result.structured_content["indices"]) > 0
