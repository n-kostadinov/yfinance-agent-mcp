from __future__ import annotations

from datetime import UTC, datetime

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from tests.fakes import FakeGateway
from tests.unit.fake_clock import FakeClock
from yfinance_agent_mcp.cache import TtlCache
from yfinance_agent_mcp.errors import NotFound, RateLimited
from yfinance_agent_mcp.models import Envelope
from yfinance_agent_mcp.tools.context import ToolContext, for_each_symbol, require_symbols


def test_symbols_are_upper_cased_and_deduplicated_in_order() -> None:
    assert require_symbols([" aapl", "SAP.de", "AAPL", "^gspc", "btc-usd"]) == [
        "AAPL",
        "SAP.DE",
        "^GSPC",
        "BTC-USD",
    ]


@pytest.mark.parametrize("symbols", [["AAPL", "drop table"], ["   "], ["$$$"]])
def test_invalid_symbols_become_an_invalid_argument_tool_error(symbols: list[str]) -> None:
    with pytest.raises(ToolError, match=r"invalid_argument: .*search_symbols"):
        require_symbols(symbols)


def fetch_or_fail(symbol: str) -> str:
    if symbol == "GONE":
        raise NotFound("$GONE: possibly delisted")
    if symbol == "SLOW":
        raise RateLimited(30)
    return f"{symbol}-data"


def test_each_symbol_failure_is_reported_next_to_the_results() -> None:
    results, errors = for_each_symbol(["AAPL", "GONE", "MSFT"], fetch_or_fail)

    assert results == ["AAPL-data", "MSFT-data"]
    assert [(e.symbol, e.error) for e in errors] == [("GONE", "not_found")]


def test_rate_limit_skips_the_remaining_symbols() -> None:
    results, errors = for_each_symbol(["AAPL", "SLOW", "MSFT", "NVDA"], fetch_or_fail)

    assert results == ["AAPL-data"]
    assert [(e.symbol, e.error) for e in errors] == [
        ("SLOW", "rate_limited"),
        ("MSFT", "rate_limited"),
        ("NVDA", "rate_limited"),
    ]


def test_failure_of_every_symbol_raises_the_first_error() -> None:
    with pytest.raises(NotFound, match="GONE"):
        for_each_symbol(["GONE"], fetch_or_fail)


class Counted(Envelope):
    value: int


def test_answer_reuses_a_cached_result_until_it_expires() -> None:
    clock = FakeClock()
    context = ToolContext(gateway=FakeGateway(), cache=TtlCache(clock=clock))
    builds = iter(range(1, 100))

    def build() -> Counted:
        return Counted(as_of=datetime(2026, 1, 1, tzinfo=UTC), value=next(builds))

    first = context.answer("quotes", {"symbols": ["AAPL"]}, build, "concise")
    cached = context.answer("quotes", {"symbols": ["AAPL"]}, build, "concise")
    clock.advance(15)
    fresh = context.answer("quotes", {"symbols": ["AAPL"]}, build, "concise")

    assert (first.value, cached.value, fresh.value) == (1, 1, 2)


def test_answer_turns_domain_errors_into_tool_errors() -> None:
    context = ToolContext(gateway=FakeGateway(), cache=TtlCache())

    def build() -> Counted:
        raise RateLimited(12)

    with pytest.raises(ToolError, match=r"rate_limited: .*Retry in 12 s"):
        context.answer("quotes", {}, build, "concise")
