from __future__ import annotations

import pytest
from mcp import Client

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_market_wide_calendars_load(live_client: Client) -> None:
    for kind in ("earnings", "economic"):
        result = await live_client.call_tool("get_events", {"kind": kind, "limit": 10})

        assert result.is_error is False, result.content
        assert result.structured_content is not None
        assert len(result.structured_content["events"]) <= 10


async def test_symbol_calendar_has_the_next_earnings_date(live_client: Client) -> None:
    result = await live_client.call_tool("get_events", {"symbols": ["AAPL"]})

    assert result.structured_content is not None
    aapl = result.structured_content["symbols"][0]
    assert aapl["calendar"]["earnings_date"]
    assert len(aapl["earnings_dates"]) > 0
