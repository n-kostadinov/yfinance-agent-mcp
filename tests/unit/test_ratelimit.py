from __future__ import annotations

import pytest

from tests.unit.fake_clock import FakeClock
from yfinance_agent_mcp.ratelimit import CooldownActive, RateLimiter


def make_limiter(clock: FakeClock, rate: float = 2.0, burst: int = 5) -> RateLimiter:
    return RateLimiter(rate, burst, clock=clock, sleep=clock.sleep)


def test_burst_passes_without_waiting_then_requests_are_paced_at_the_rate() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock, rate=2.0, burst=5)

    for _ in range(7):
        limiter.acquire()

    assert clock.sleeps == [0.5, 0.5]


def test_idle_time_refills_the_burst() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock, rate=2.0, burst=5)
    for _ in range(5):
        limiter.acquire()

    clock.advance(10)
    for _ in range(5):
        limiter.acquire()

    assert clock.sleeps == []


def test_rate_limit_pauses_every_request_until_the_pause_ends() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)

    pause = limiter.report_rate_limited()
    clock.advance(29.5)
    with pytest.raises(CooldownActive) as paused:
        limiter.acquire()
    clock.advance(0.5)
    limiter.acquire()

    assert pause == 30.0
    assert paused.value.retry_after == pytest.approx(0.5)
    assert limiter.cooldown_remaining() == 0.0


def test_consecutive_rate_limits_double_the_pause_up_to_five_minutes() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    pauses = []

    for _ in range(6):
        pauses.append(limiter.report_rate_limited())
        clock.advance(pauses[-1])

    assert pauses == [30.0, 60.0, 120.0, 240.0, 300.0, 300.0]


def test_rate_limit_reported_during_a_pause_does_not_lengthen_it() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    limiter.report_rate_limited()

    clock.advance(10)
    remaining = limiter.report_rate_limited()
    clock.advance(20)
    next_pause = limiter.report_rate_limited()

    assert remaining == pytest.approx(20.0)
    assert next_pause == 60.0


def test_successful_request_resets_the_pause_to_its_first_length() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    clock.advance(limiter.report_rate_limited())
    clock.advance(limiter.report_rate_limited())

    limiter.report_success()

    assert limiter.report_rate_limited() == 30.0
