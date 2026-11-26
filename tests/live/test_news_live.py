from __future__ import annotations

import pytest
from mcp import Client

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_symbol_news_has_dated_linked_items(live_client: Client) -> None:
    result = await live_client.call_tool("get_news", {"symbols": ["AAPL"], "count": 5})

    assert result.structured_content is not None
    items = result.structured_content["items"]
    assert len(items) >= 1
    assert all(item["published_at"] and item["url"] for item in items)
    assert all(item["untrusted"]["title"] for item in items)


async def test_query_news_finds_articles(live_client: Client) -> None:
    result = await live_client.call_tool("get_news", {"query": "nvidia earnings", "count": 5})

    assert result.structured_content is not None
    assert len(result.structured_content["items"]) >= 1
