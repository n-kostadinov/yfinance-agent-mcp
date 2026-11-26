from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from mcp import Client

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_one_year_daily_summary_has_long_term_indicators(live_client: Client) -> None:
    result = await live_client.call_tool("get_price_history", {"symbols": ["AAPL"], "period": "1y"})

    assert result.structured_content is not None
    prices = result.structured_content["prices"][0]
    summary = prices["summary"]
    assert summary["sma_200"] is not None
    assert 0 <= summary["rsi_14"] <= 100
    assert len(prices["bars"]) == 20
    last_bar = datetime.fromisoformat(prices["last_bar_time"])
    assert datetime.now(UTC) - last_bar < timedelta(days=7)


async def test_intraday_bars_for_five_days(live_client: Client) -> None:
    result = await live_client.call_tool(
        "get_price_history",
        {"symbols": ["MSFT"], "period": "5d", "interval": "15m", "mode": "bars", "bars": 50},
    )

    assert result.structured_content is not None
    prices = result.structured_content["prices"][0]
    assert prices["interval"] == "15m"
    assert len(prices["bars"]) == 50
