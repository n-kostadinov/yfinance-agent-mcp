from __future__ import annotations

import pytest
from mcp import Client

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_dividends_are_newest_first(live_client: Client) -> None:
    result = await live_client.call_tool(
        "get_ticker_dataset", {"symbol": "AAPL", "dataset": "dividends", "limit": 5}
    )

    assert result.structured_content is not None
    dates = [row["date"] for row in result.structured_content["rows"]]
    assert len(dates) == 5
    assert dates == sorted(dates, reverse=True)


async def test_holders_isin_and_fund_holdings(live_client: Client) -> None:
    holders = await live_client.call_tool(
        "get_ticker_dataset", {"symbol": "AAPL", "dataset": "institutional_holders"}
    )
    isin = await live_client.call_tool("get_ticker_dataset", {"symbol": "AAPL", "dataset": "isin"})
    fund = await live_client.call_tool(
        "get_ticker_dataset", {"symbol": "SPY", "dataset": "fund_top_holdings"}
    )

    assert holders.structured_content is not None
    assert isin.structured_content is not None
    assert fund.structured_content is not None
    assert len(holders.structured_content["rows"]) > 0
    assert isin.structured_content["data"] == "US0378331005"
    assert len(fund.structured_content["rows"]) > 0


async def test_fund_dataset_of_a_stock_is_not_found(live_client: Client) -> None:
    result = await live_client.call_tool(
        "get_ticker_dataset", {"symbol": "AAPL", "dataset": "fund_top_holdings"}
    )

    assert result.is_error is True
