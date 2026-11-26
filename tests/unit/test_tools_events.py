from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from tests.fakes import FakeGateway
from yfinance_agent_mcp.errors import InvalidArgument
from yfinance_agent_mcp.gateway import TickerEvents
from yfinance_agent_mcp.tools.events import EventKind, build_events, check_event_range

TODAY = date(2026, 11, 24)
NEXT_WEEK = check_event_range("earnings", None, None, False, TODAY)


def earnings_calendar(rows: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Company": [f"Company {n}" for n in range(rows)],
            "Event Start Date": [pd.Timestamp("2026-12-01 21:00", tz="UTC")] * rows,
            "EPS Estimate": [1.1] * rows,
            "Surprise(%)": [float("nan")] * rows,
        },
        index=pd.Index([f"S{n}" for n in range(rows)], name="Symbol"),
    )


def test_default_range_is_the_next_seven_days() -> None:
    assert (NEXT_WEEK.start, NEXT_WEEK.end) == (TODAY, TODAY + timedelta(days=7))


@pytest.mark.parametrize(
    ("kind", "start", "end", "has_symbols", "reason"),
    [
        ("earnings", TODAY, TODAY - timedelta(days=1), False, "after"),
        ("ipo", TODAY, TODAY + timedelta(days=120), False, "at most 92 days"),
        ("ipo", None, None, True, "only for kind 'earnings'"),
    ],
)
def test_impossible_requests_are_rejected(
    kind: EventKind, start: date | None, end: date | None, has_symbols: bool, reason: str
) -> None:
    with pytest.raises(InvalidArgument, match=reason):
        check_event_range(kind, start, end, has_symbols, TODAY)


def test_market_calendar_rows_become_readable_records_up_to_the_limit() -> None:
    gateway = FakeGateway()
    gateway.calendars["earnings"] = earnings_calendar(80)

    result = build_events(gateway, "earnings", NEXT_WEEK, [], 50)

    assert len(result.events) == 50
    assert result.events[0] == {
        "symbol": "S0",
        "company": "Company 0",
        "event_start_date": "2026-12-01T21:00:00Z",
        "eps_estimate": 1.1,
        "surprise_pct": None,
    }
    assert (result.start, result.end) == ("2026-11-24", "2026-12-01")


def test_symbol_calendars_include_estimates_and_earnings_history() -> None:
    gateway = FakeGateway()
    earnings = pd.DataFrame(
        {"EPS Estimate": [2.9], "Reported EPS": [3.1], "Surprise(%)": [6.9]},
        index=pd.Index(
            [pd.Timestamp("2026-10-30 16:00", tz="America/New_York")], name="Earnings Date"
        ),
    )
    gateway.ticker_calendars["AAPL"] = TickerEvents(
        calendar={"Earnings Date": [date(2027, 1, 28)], "Earnings Average": 2.91},
        earnings_dates=earnings,
    )

    result = build_events(gateway, "earnings", NEXT_WEEK, ["AAPL", "GONE"], 50)

    aapl = result.symbols[0]
    assert aapl.calendar == {"earnings_date": ["2027-01-28"], "earnings_average": 2.91}
    assert aapl.earnings_dates == [
        {
            "earnings_date": "2026-10-30T20:00:00Z",
            "eps_estimate": 2.9,
            "reported_eps": 3.1,
            "surprise_pct": 6.9,
        }
    ]
    assert [(e.symbol, e.error) for e in result.errors] == [("GONE", "not_found")]
