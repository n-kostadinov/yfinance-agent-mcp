from __future__ import annotations

import pytest
from mcp import Client

from tests.fakes import FakeGateway
from yfinance_agent_mcp.models import MarketIndex, MarketStatus, Quote, SymbolMatch

pytestmark = pytest.mark.anyio


async def test_search_symbols_returns_the_matches(
    client: Client, fake_gateway: FakeGateway
) -> None:
    fake_gateway.symbol_matches["nvidia"] = [SymbolMatch(symbol="NVDA", name="NVIDIA Corporation")]

    result = await client.call_tool("search_symbols", {"query": "nvidia"})

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["matches"] == [
        {
            "symbol": "NVDA",
            "name": "NVIDIA Corporation",
            "type": None,
            "exchange": None,
            "sector": None,
            "industry": None,
        }
    ]


async def test_get_quotes_returns_quotes_and_per_symbol_errors(
    client: Client, fake_gateway: FakeGateway
) -> None:
    fake_gateway.quotes["AAPL"] = Quote(symbol="AAPL", price=271.5, currency="USD")

    result = await client.call_tool("get_quotes", {"symbols": ["aapl", "GONE"]})

    assert result.structured_content is not None
    assert [q["symbol"] for q in result.structured_content["quotes"]] == ["AAPL"]
    assert result.structured_content["errors"][0]["symbol"] == "GONE"
    assert result.structured_content["as_of"].endswith("Z")


async def test_get_market_overview_returns_status_and_indices(
    client: Client, fake_gateway: FakeGateway
) -> None:
    fake_gateway.markets["US"] = (
        MarketStatus(name="U.S. markets", state="open"),
        [MarketIndex(symbol="^GSPC", price=6_000.0)],
    )

    result = await client.call_tool("get_market_overview", {"region": "US"})

    assert result.structured_content is not None
    assert result.structured_content["status"]["state"] == "open"
    assert result.structured_content["indices"][0]["symbol"] == "^GSPC"
