from __future__ import annotations

import pytest
from mcp import Client

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_bitcoin_streams_around_the_clock_without_touching_stdout(
    live_client: Client, capfd: pytest.CaptureFixture[str]
) -> None:
    result = await live_client.call_tool(
        "get_live_quotes", {"symbols": ["BTC-USD"], "wait_seconds": 10}
    )

    assert result.structured_content is not None
    ticks = result.structured_content["ticks"]
    assert len(ticks) == 1
    assert ticks[0]["price"] > 0
    assert capfd.readouterr().out == ""
