from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.fakes import FakeGateway, make_history
from yfinance_agent_mcp.errors import InvalidArgument
from yfinance_agent_mcp.tools.prices import (
    Interval,
    Period,
    build_price_history,
    check_price_request,
)

TODAY = date(2026, 11, 24)
DAILY = check_price_request("6mo", "1d", None, None, TODAY)


def gateway_with(symbol: str, closes: list[float], freq: str = "D") -> FakeGateway:
    gateway = FakeGateway()
    gateway.histories[symbol] = make_history(symbol, closes, freq=freq)
    return gateway


def test_summary_mode_returns_indicators_and_the_last_twenty_bars() -> None:
    gateway = gateway_with("AAPL", [100.0 + day for day in range(60)])

    result = build_price_history(gateway, ["AAPL"], DAILY, "summary", 20, 20_000)

    prices = result.prices[0]
    assert prices.summary is not None
    assert prices.summary.bars == 60
    assert prices.bar_count == 60
    assert len(prices.bars) == 20
    assert prices.bars[-1].close == 159.0
    assert prices.bars[-1].time == prices.last_bar_time


def test_bars_mode_returns_only_the_requested_bars() -> None:
    gateway = gateway_with("AAPL", [100.0 + day for day in range(60)])

    result = build_price_history(gateway, ["AAPL"], DAILY, "bars", 5, 20_000)

    assert result.prices[0].summary is None
    assert [bar.close for bar in result.prices[0].bars] == [155.0, 156.0, 157.0, 158.0, 159.0]


def test_symbols_without_prices_are_listed_as_errors() -> None:
    gateway = gateway_with("AAPL", [100.0, 101.0])

    result = build_price_history(gateway, ["AAPL", "GONE"], DAILY, "summary", 20, 20_000)

    assert [p.symbol for p in result.prices] == ["AAPL"]
    assert [(e.symbol, e.error) for e in result.errors] == [("GONE", "not_found")]


def test_five_days_of_minute_bars_fit_the_default_budget() -> None:
    gateway = gateway_with("AAPL", [200.0 + i / 100 for i in range(1_950)], freq="min")
    request = check_price_request("5d", "1m", None, None, TODAY)

    result = build_price_history(gateway, ["AAPL"], request, "bars", 500, 20_000)

    assert len(result.model_dump_json()) <= 20_000
    assert 0 < len(result.prices[0].bars) < 500
    assert any("to fit the response budget" in warning for warning in result.warnings)


def test_a_start_date_overrides_the_period() -> None:
    request = check_price_request("1y", "1d", TODAY - timedelta(days=30), None, TODAY)

    assert (request.period, request.start, request.end) == (None, TODAY - timedelta(days=30), None)


@pytest.mark.parametrize(
    ("period", "interval", "start", "end", "reason"),
    [
        ("3mo", "5m", None, None, "last 60 days"),
        (None, "1h", TODAY - timedelta(days=90), None, "last 60 days"),
        ("1mo", "1m", None, None, "7 days"),
        (None, "1m", TODAY - timedelta(days=10), None, "7 days"),
        (None, "1d", TODAY, TODAY - timedelta(days=1), "after"),
        (None, "1d", None, TODAY, "end needs a start"),
    ],
)
def test_impossible_ranges_are_rejected_before_asking_yahoo(
    period: Period | None, interval: Interval, start: date | None, end: date | None, reason: str
) -> None:
    with pytest.raises(InvalidArgument, match=reason):
        check_price_request(period, interval, start, end, TODAY)
