from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

from tests.unit.fake_clock import FakeClock
from yfinance_agent_mcp.cache import DEFAULT_TTLS, TtlCache


def versions(prefix: str = "v") -> Callable[[], str]:
    """A compute function that returns a new value on every call: v1, v2, ..."""
    counter: Iterator[int] = iter(range(1, 1_000))
    return lambda: f"{prefix}{next(counter)}"


def test_default_times_to_live_match_the_documented_categories() -> None:
    assert dict(DEFAULT_TTLS) == {
        "quotes": 15,
        "history_intraday": 30,
        "history_daily": 300,
        "news": 120,
        "search": 120,
        "market": 30,
        "screen": 60,
        "options": 60,
        "events": 3_600,
        "analysts": 3_600,
        "fundamentals": 21_600,
        "datasets": 21_600,
        "sector": 21_600,
    }


def test_cached_value_is_returned_until_its_category_expires() -> None:
    clock = FakeClock()
    cache = TtlCache(clock=clock)
    compute = versions()

    first = cache.get_or_compute("quotes", {"symbols": ["AAPL"]}, compute)
    clock.advance(14.9)
    before_expiry = cache.get_or_compute("quotes", {"symbols": ["AAPL"]}, compute)
    clock.advance(0.1)
    after_expiry = cache.get_or_compute("quotes", {"symbols": ["AAPL"]}, compute)

    assert (first, before_expiry, after_expiry) == ("v1", "v1", "v2")


def test_different_arguments_are_cached_separately() -> None:
    cache = TtlCache(clock=FakeClock())
    compute = versions()

    aapl = cache.get_or_compute("quotes", {"symbols": ["AAPL"]}, compute)
    msft = cache.get_or_compute("quotes", {"symbols": ["MSFT"]}, compute)

    assert (aapl, msft) == ("v1", "v2")


def test_argument_order_does_not_change_the_key() -> None:
    cache = TtlCache(clock=FakeClock())
    compute = versions()

    first = cache.get_or_compute("history_daily", {"period": "1y", "interval": "1d"}, compute)
    second = cache.get_or_compute("history_daily", {"interval": "1d", "period": "1y"}, compute)

    assert first == second == "v1"


def test_failed_computation_is_not_cached() -> None:
    cache = TtlCache(clock=FakeClock())

    def fail() -> str:
        raise TimeoutError("Yahoo did not answer")

    with pytest.raises(TimeoutError):
        cache.get_or_compute("news", {"symbols": ["AAPL"]}, fail)
    value = cache.get_or_compute("news", {"symbols": ["AAPL"]}, lambda: "fresh")

    assert value == "fresh"


def test_override_replaces_the_default_time_to_live() -> None:
    clock = FakeClock()
    cache = TtlCache({"quotes": 5}, clock=clock)
    compute = versions()

    cache.get_or_compute("quotes", {}, compute)
    clock.advance(5)

    assert cache.get_or_compute("quotes", {}, compute) == "v2"


def test_zero_time_to_live_disables_caching() -> None:
    cache = TtlCache({"market": 0}, clock=FakeClock())
    compute = versions()

    first = cache.get_or_compute("market", {"region": "US"}, compute)
    second = cache.get_or_compute("market", {"region": "US"}, compute)

    assert (first, second) == ("v1", "v2")


def test_unknown_override_category_is_rejected_with_the_valid_names() -> None:
    with pytest.raises(ValueError, match=r"unknown cache categories \['quote'\].*quotes"):
        TtlCache({"quote": 5})


def test_oldest_entry_is_evicted_when_the_cache_is_full() -> None:
    cache = TtlCache(clock=FakeClock(), max_entries=2)
    compute = versions()
    cache.get_or_compute("quotes", {"symbols": ["A"]}, compute)
    cache.get_or_compute("quotes", {"symbols": ["B"]}, compute)

    cache.get_or_compute("quotes", {"symbols": ["C"]}, compute)

    assert cache.get_or_compute("quotes", {"symbols": ["B"]}, compute) == "v2"
    assert cache.get_or_compute("quotes", {"symbols": ["A"]}, compute) == "v4"
