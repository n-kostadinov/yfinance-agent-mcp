from __future__ import annotations

import json

import pytest
from mcp import Client

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_day_gainers_fit_the_default_budget(live_client: Client) -> None:
    result = await live_client.call_tool("screen_securities", {"preset": "day_gainers"})

    assert result.structured_content is not None
    assert 0 < len(result.structured_content["rows"]) <= 25
    assert len(json.dumps(result.structured_content)) <= 20_000


async def test_custom_query_screens_us_equities(live_client: Client) -> None:
    query = {
        "operator": "and",
        "operands": [
            {"operator": "gt", "operands": ["intradaymarketcap", 10_000_000_000]},
            {"operator": "eq", "operands": ["region", "us"]},
        ],
    }

    result = await live_client.call_tool(
        "screen_securities", {"query": query, "sort_field": "intradaymarketcap", "count": 5}
    )

    assert result.structured_content is not None
    assert len(result.structured_content["rows"]) == 5


async def test_technology_sector_and_semiconductor_industry(live_client: Client) -> None:
    sector = await live_client.call_tool(
        "get_sector_industry", {"kind": "sector", "key": "technology"}
    )
    industry = await live_client.call_tool(
        "get_sector_industry", {"kind": "industry", "key": "semiconductors"}
    )

    assert sector.structured_content is not None
    assert industry.structured_content is not None
    assert len(sector.structured_content["top_companies"]) > 0
    assert len(sector.structured_content["industries"]) > 0
    assert len(industry.structured_content["top_performing_companies"]) > 0
