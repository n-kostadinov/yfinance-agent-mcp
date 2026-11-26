from __future__ import annotations

import pandas as pd
import pytest
from mcp import Client
from mcp.types import TextContent

from tests.fakes import FakeGateway

pytestmark = pytest.mark.anyio


async def test_get_events_returns_the_economic_calendar(
    client: Client, fake_gateway: FakeGateway
) -> None:
    fake_gateway.calendars["economic"] = pd.DataFrame(
        {"Region": ["US"], "Expected": [0.3], "Last": [0.2]},
        index=pd.Index(["CPI"], name="Event"),
    )

    result = await client.call_tool("get_events", {"kind": "economic"})

    assert result.structured_content is not None
    assert result.structured_content["events"] == [
        {"event": "CPI", "region": "US", "expected": 0.3, "last": 0.2}
    ]


async def test_invalid_date_range_is_an_invalid_argument_error(client: Client) -> None:
    result = await client.call_tool(
        "get_events", {"kind": "earnings", "start": "2026-12-10", "end": "2026-12-01"}
    )

    assert result.is_error is True
    text = result.content[0]
    assert isinstance(text, TextContent)
    assert "invalid_argument: start 2026-12-10 is after end 2026-12-01" in text.text
