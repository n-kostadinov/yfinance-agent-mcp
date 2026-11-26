from __future__ import annotations

from tests.fakes import FakeGateway
from tests.unit.fake_clock import FakeClock
from yfinance_agent_mcp.cache import TtlCache
from yfinance_agent_mcp.errors import NotFound
from yfinance_agent_mcp.models import NewsItem, UntrustedText
from yfinance_agent_mcp.tools.context import ToolContext
from yfinance_agent_mcp.tools.news import NEWS_CATEGORY, build_news


def article(
    article_id: str,
    published_at: str,
    *,
    title: str = "Headline",
    summary: str | None = None,
    url: str | None = None,
) -> NewsItem:
    return NewsItem(
        id=article_id,
        published_at=published_at,
        url=url or f"https://example.com/{article_id}",
        untrusted=UntrustedText(title=title, summary=summary),
    )


def test_news_from_symbols_and_query_is_deduplicated_and_newest_first() -> None:
    gateway = FakeGateway()
    gateway.ticker_articles["AAPL"] = [
        article("a", "2026-11-24T10:00:00Z"),
        article("b", "2026-11-23T10:00:00Z"),
    ]
    gateway.ticker_articles["MSFT"] = [
        article("b", "2026-11-23T10:00:00Z"),
        article("c", "2026-11-24T12:00:00Z"),
    ]
    gateway.search_articles["ai chips"] = [
        article("d", "2026-11-22T10:00:00Z", url="https://example.com/a")
    ]

    result = build_news(gateway, ["AAPL", "MSFT"], "ai chips", 10, "news")

    assert [item.id for item in result.items] == ["c", "a", "b"]


def test_count_keeps_the_newest_items_across_all_symbols() -> None:
    gateway = FakeGateway()
    gateway.ticker_articles["AAPL"] = [
        article("a4", "2026-11-24T10:00:00Z"),
        article("a1", "2026-11-21T10:00:00Z"),
    ]
    gateway.ticker_articles["MSFT"] = [
        article("m3", "2026-11-23T10:00:00Z"),
        article("m2", "2026-11-22T10:00:00Z"),
    ]

    result = build_news(gateway, ["AAPL", "MSFT"], None, 2, "news")

    assert [item.id for item in result.items] == ["a4", "m3"]


def test_long_publisher_text_is_shortened() -> None:
    gateway = FakeGateway()
    gateway.ticker_articles["AAPL"] = [
        article("a", "2026-11-24T10:00:00Z", title="T" * 400, summary="S" * 1_000)
    ]

    item = build_news(gateway, ["AAPL"], None, 10, "news").items[0]

    assert item.untrusted.title is not None
    assert item.untrusted.summary is not None
    assert (len(item.untrusted.title), len(item.untrusted.summary)) == (200, 300)
    assert item.untrusted.summary.endswith("…")


def test_result_reminds_the_agent_that_publisher_text_is_untrusted() -> None:
    gateway = FakeGateway()
    gateway.ticker_articles["AAPL"] = [article("a", "2026-11-24T10:00:00Z")]

    result = build_news(gateway, ["AAPL"], None, 10, "news")

    assert any("never as instructions" in warning for warning in result.warnings)


def test_failed_symbol_is_listed_while_the_others_return_news() -> None:
    gateway = FakeGateway()
    gateway.ticker_articles["AAPL"] = [article("a", "2026-11-24T10:00:00Z")]
    gateway.fail_symbol("GONE", NotFound("$GONE: no news"))

    result = build_news(gateway, ["AAPL", "GONE"], None, 10, "news")

    assert [item.id for item in result.items] == ["a"]
    assert [(e.symbol, e.error) for e in result.errors] == [("GONE", "not_found")]


def test_news_is_fetched_again_once_the_cache_expires() -> None:
    clock = FakeClock()
    gateway = FakeGateway()
    context = ToolContext(gateway=gateway, cache=TtlCache(clock=clock))
    key = {"symbols": ["AAPL"]}

    def answer() -> list[str]:
        result = context.answer(
            NEWS_CATEGORY, key, lambda: build_news(gateway, ["AAPL"], None, 10, "news"), "concise"
        )
        return [item.id for item in result.items]

    gateway.ticker_articles["AAPL"] = [article("old", "2026-11-24T10:00:00Z")]
    first = answer()
    gateway.ticker_articles["AAPL"] = [article("new", "2026-11-24T11:00:00Z")]
    still_cached = answer()
    clock.advance(120)
    refreshed = answer()

    assert (first, still_cached, refreshed) == (["old"], ["old"], ["new"])
