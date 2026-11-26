from __future__ import annotations

import pandas as pd
import pytest
from mcp import Client
from mcp.types import TextContent

from tests.fakes import FakeGateway

pytestmark = pytest.mark.anyio


async def test_get_ticker_dataset_returns_paged_rows(
    client: Client, fake_gateway: FakeGateway
) -> None:
    fake_gateway.datasets[("AAPL", "insider_transactions")] = pd.DataFrame(
        {"Insider": ["COOK TIMOTHY D"], "Shares": [100_000], "Transaction": ["Sale"]}
    )

    result = await client.call_tool(
        "get_ticker_dataset", {"symbol": "AAPL", "dataset": "insider_transactions"}
    )

    assert result.structured_content is not None
    assert result.structured_content["rows"] == [
        {"insider": "COOK TIMOTHY D", "shares": 100_000, "transaction": "Sale"}
    ]


async def test_unknown_dataset_is_rejected_with_the_valid_names(client: Client) -> None:
    result = await client.call_tool("get_ticker_dataset", {"symbol": "AAPL", "dataset": "holders"})

    assert result.is_error is True
    text = result.content[0]
    assert isinstance(text, TextContent)
    assert "major_holders" in text.text
