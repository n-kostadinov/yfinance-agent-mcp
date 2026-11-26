from __future__ import annotations

import pandas as pd
import pytest
from mcp import Client

from tests.fakes import FakeGateway
from yfinance_agent_mcp.gateway import AnalystData

pytestmark = pytest.mark.anyio


async def test_get_fundamentals_returns_statement_periods(
    client: Client, fake_gateway: FakeGateway
) -> None:
    fake_gateway.statements[("MSFT", "cashflow", "yearly")] = pd.DataFrame(
        {pd.Timestamp("2026-06-30"): [136e9, -64e9, 72e9]},
        index=["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow"],
    )

    result = await client.call_tool(
        "get_fundamentals", {"symbol": "msft", "statement": "cashflow", "freq": "yearly"}
    )

    assert result.structured_content is not None
    assert result.structured_content["periods"] == [
        {
            "period": "2026-06-30",
            "operating_cash_flow": 136e9,
            "capital_expenditure": -64e9,
            "free_cash_flow": 72e9,
        }
    ]


async def test_get_analyst_view_returns_targets_and_ratings(
    client: Client, fake_gateway: FakeGateway
) -> None:
    fake_gateway.analysts["MSFT"] = AnalystData(
        price_targets={"mean": 600.0},
        recommendations=None,
        rating_changes=None,
        earnings_estimate=None,
        revenue_estimate=None,
        eps_trend=None,
        eps_revisions=None,
        growth_estimates=None,
    )

    result = await client.call_tool("get_analyst_view", {"symbol": "MSFT"})

    assert result.structured_content is not None
    assert result.structured_content["price_targets"] == {"mean": 600.0}
    assert result.structured_content["rating_changes"] == []
