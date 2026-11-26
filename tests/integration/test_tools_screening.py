from __future__ import annotations

import pandas as pd
import pytest
from mcp import Client

from tests.fakes import FakeGateway
from yfinance_agent_mcp.gateway import ScreenPage, SectorData
from yfinance_agent_mcp.models import ScreenRow

pytestmark = pytest.mark.anyio


async def test_screen_securities_runs_a_predefined_screen(
    client: Client, fake_gateway: FakeGateway
) -> None:
    fake_gateway.screens["most_actives"] = ScreenPage(
        title="Most Actives", total=50, rows=[ScreenRow(symbol="NVDA", price=165.0)]
    )

    result = await client.call_tool("screen_securities", {"preset": "most_actives"})

    assert result.structured_content is not None
    assert result.structured_content["total"] == 50
    assert result.structured_content["rows"][0]["symbol"] == "NVDA"


async def test_get_sector_industry_returns_an_industry_leaderboard(
    client: Client, fake_gateway: FakeGateway
) -> None:
    performers = pd.DataFrame(
        {"name": ["NVIDIA"], "ytd return": [0.35], "last price": [165.0], "target price": [210.0]},
        index=pd.Index(["NVDA"], name="symbol"),
    )
    fake_gateway.sectors[("industry", "semiconductors")] = SectorData(
        kind="industry",
        key="semiconductors",
        name="Semiconductors",
        sector_key="technology",
        sector_name="Technology",
        overview={"companies_count": 60},
        tables={"top_performing_companies": performers},
        funds={},
    )

    result = await client.call_tool(
        "get_sector_industry", {"kind": "industry", "key": "semiconductors"}
    )

    assert result.structured_content is not None
    assert result.structured_content["sector_key"] == "technology"
    assert result.structured_content["top_performing_companies"][0]["target_price"] == 210.0
