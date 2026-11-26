from __future__ import annotations

import pandas as pd
import pytest
from mcp import Client

from tests.fakes import FakeGateway
from yfinance_agent_mcp.gateway import OptionChain

pytestmark = pytest.mark.anyio


async def test_get_options_returns_the_chain_around_the_price(
    client: Client, fake_gateway: FakeGateway
) -> None:
    side = pd.DataFrame(
        {"contractSymbol": ["AAPL261128C00270000"], "strike": [270.0], "impliedVolatility": [0.25]}
    )
    fake_gateway.expirations["AAPL"] = ["2026-11-28"]
    fake_gateway.chains[("AAPL", "2026-11-28")] = OptionChain(
        calls=side, puts=side, underlying={"regularMarketPrice": 271.5}
    )

    result = await client.call_tool("get_options", {"symbol": "AAPL"})

    assert result.structured_content is not None
    assert result.structured_content["expiry"] == "2026-11-28"
    assert result.structured_content["calls"][0]["implied_volatility"] == 0.25
