from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from tests.fakes import FakeStream
from yfinance_agent_mcp.errors import UpstreamError
from yfinance_agent_mcp.live import LiveQuotes, Tick
from yfinance_agent_mcp.tools.streaming import build_live_quotes

pytestmark = pytest.mark.anyio

START = datetime(2026, 11, 24, 15, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


class Streams:
    """Opens FakeStreams with canned ticks and remembers them, newest last."""

    def __init__(self, ticks: dict[str, dict[str, object]] | None = None) -> None:
        self.ticks = ticks or {}
        self.opened: list[FakeStream] = []

    def __call__(self) -> FakeStream:
        stream = FakeStream(self.ticks)
        self.opened.append(stream)
        return stream


BTC = {"id": "BTC-USD", "price": 87_000.5, "time": "1795600000000"}


async def test_first_request_subscribes_and_returns_the_tick_that_arrives() -> None:
    streams = Streams({"BTC-USD": BTC})
    live = LiveQuotes(streams, now=Clock())

    ticks, missing = await live.latest(["BTC-USD"], wait_seconds=1)

    assert ticks["BTC-USD"].message == BTC
    assert missing == []
    assert streams.opened[0].subscribed == {"BTC-USD"}
    await live.aclose()


async def test_symbols_without_a_tick_are_missing_after_the_wait() -> None:
    live = LiveQuotes(Streams(), now=Clock())

    ticks, missing = await live.latest(["AAPL"], wait_seconds=0.05)

    assert (ticks, missing) == ({}, ["AAPL"])
    await live.aclose()


async def test_the_latest_tick_of_a_symbol_wins() -> None:
    streams = Streams({"BTC-USD": BTC})
    live = LiveQuotes(streams, now=Clock())
    await live.latest(["BTC-USD"], wait_seconds=1)

    streams.opened[0].push({"id": "BTC-USD", "price": 87_100.0})
    ticks, _ = await live.latest(["BTC-USD"], wait_seconds=0)

    assert ticks["BTC-USD"].message["price"] == 87_100.0
    await live.aclose()


async def test_symbols_nobody_asked_for_in_ten_minutes_are_unsubscribed() -> None:
    clock = Clock()
    streams = Streams({"BTC-USD": BTC, "ETH-USD": {"id": "ETH-USD", "price": 3_000.0}})
    live = LiveQuotes(streams, now=clock)
    await live.latest(["BTC-USD", "ETH-USD"], wait_seconds=1)

    clock.now += timedelta(minutes=5)
    await live.latest(["BTC-USD"], wait_seconds=0)
    clock.now += timedelta(minutes=6)
    await live.latest(["BTC-USD"], wait_seconds=0)

    assert streams.opened[0].subscribed == {"BTC-USD"}
    await live.aclose()


async def test_a_dropped_stream_is_reopened_with_its_subscriptions() -> None:
    broken = FakeStream({"BTC-USD": BTC})
    broken.listen_error = ConnectionError("feed dropped")
    healthy = FakeStream({"BTC-USD": {"id": "BTC-USD", "price": 90_000.0}})
    unopened = [healthy, broken]  # pop() hands out the broken stream first
    live = LiveQuotes(unopened.pop, now=Clock())
    await live.latest(["BTC-USD"], wait_seconds=1)

    await live.latest(["BTC-USD"], wait_seconds=0)  # notices the drop and reconnects
    await asyncio.sleep(0)  # let the new stream's listener deliver its first tick
    ticks, _ = await live.latest(["BTC-USD"], wait_seconds=0)

    assert healthy.subscribed == {"BTC-USD"}
    assert ticks["BTC-USD"].message["price"] == 90_000.0
    await live.aclose()


async def test_close_stops_listening_and_closes_the_stream() -> None:
    streams = Streams({"BTC-USD": BTC})
    live = LiveQuotes(streams, now=Clock())
    await live.latest(["BTC-USD"], wait_seconds=1)

    await live.aclose()

    assert streams.opened[0].closed is True


async def test_a_stream_that_cannot_open_is_an_upstream_error() -> None:
    def refuse() -> FakeStream:
        raise OSError("connection refused")

    live = LiveQuotes(refuse, now=Clock())

    with pytest.raises(UpstreamError, match="live price stream"):
        await live.latest(["BTC-USD"], wait_seconds=0)


def test_result_reports_ticks_with_their_age_and_the_missing_symbols() -> None:
    tick = Tick(
        message={
            "id": "BTC-USD",
            "price": 87_000.5,
            "change_percent": 1.25,
            "time": "1795600000000",
        },
        received_at=START,
    )

    result = build_live_quotes({"BTC-USD": tick}, ["AAPL"], START + timedelta(seconds=4), 3)

    assert result.ticks[0].model_dump() == {
        "symbol": "BTC-USD",
        "price": 87_000.5,
        "change_pct": 1.25,
        "day_volume": None,
        "market_hours": None,
        "exchange_time": "2026-11-25T09:46:40Z",
        "received_at": "2026-11-24T15:00:00Z",
        "age_seconds": 4.0,
    }
    assert result.missing == ["AAPL"]
    assert any("AAPL" in warning for warning in result.warnings)
