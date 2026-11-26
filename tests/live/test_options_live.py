from __future__ import annotations

import pytest
from mcp import Client

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_nearest_chain_brackets_the_current_price(live_client: Client) -> None:
    result = await live_client.call_tool("get_options", {"symbol": "AAPL"})

    assert result.structured_content is not None
    content = result.structured_content
    assert content["expirations"][0] == content["expiry"]
    strikes = [row["strike"] for row in content["calls"]]
    assert 0 < len(strikes) <= 20
    assert min(strikes) <= content["underlying_price"] <= max(strikes)
