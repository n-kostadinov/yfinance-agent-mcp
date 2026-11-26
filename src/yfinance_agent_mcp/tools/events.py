"""Upcoming earnings, IPOs, economic events and splits, market-wide or per symbol."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Annotated, Literal

import pandas as pd
from mcp.server import MCPServer
from pydantic import Field, JsonValue

from yfinance_agent_mcp.errors import InvalidArgument
from yfinance_agent_mcp.gateway import MarketDataGateway, TickerEvents
from yfinance_agent_mcp.models import EventsResult, SymbolEvents
from yfinance_agent_mcp.shaping import frame_to_records, snake_case, to_json_value
from yfinance_agent_mcp.tools.context import (
    READ_ONLY,
    ResponseFormatParam,
    ToolContext,
    for_each_symbol,
    require_symbols,
    utc_now,
)

EventKind = Literal["earnings", "ipo", "economic", "splits"]
_DEFAULT_DAYS = 7
_MAX_DAYS = 92
_EARNINGS_HISTORY = 8


@dataclass(frozen=True)
class EventRange:
    start: date
    end: date


def check_event_range(
    kind: EventKind, start: date | None, end: date | None, has_symbols: bool, today: date
) -> EventRange:
    """Default to the next 7 days; refuse ranges and combinations Yahoo cannot answer."""
    if has_symbols and kind != "earnings":
        raise InvalidArgument(
            "symbols work only for kind 'earnings'; leave them out for other kinds"
        )
    first = start or today
    last = end or first + timedelta(days=_DEFAULT_DAYS)
    if first > last:
        raise InvalidArgument(f"start {first} is after end {last}")
    if (last - first).days > _MAX_DAYS:
        raise InvalidArgument(
            f"a range covers at most {_MAX_DAYS} days; split it into smaller ranges"
        )
    return EventRange(start=first, end=last)


def build_events(
    gateway: MarketDataGateway,
    kind: EventKind,
    window: EventRange,
    symbols: Sequence[str],
    limit: int,
) -> EventsResult:
    result = EventsResult(
        as_of=utc_now(), kind=kind, start=window.start.isoformat(), end=window.end.isoformat()
    )
    if symbols:
        calendars, errors = for_each_symbol(
            symbols, lambda symbol: (symbol, gateway.ticker_events(symbol, _EARNINGS_HISTORY))
        )
        result.symbols = [_symbol_events(symbol, events) for symbol, events in calendars]
        result.errors = errors
        return result
    frame = gateway.calendar_events(kind, window.start, window.end, limit)
    result.events = _records(frame, limit)
    if not result.events:
        result.warnings.append(f"No {kind} events between {window.start} and {window.end}.")
    return result


def _symbol_events(symbol: str, events: TickerEvents) -> SymbolEvents:
    calendar = {snake_case(name): to_json_value(value) for name, value in events.calendar.items()}
    return SymbolEvents(
        symbol=symbol,
        calendar=calendar,  # type: ignore[arg-type]
        earnings_dates=_records(events.earnings_dates, _EARNINGS_HISTORY),
    )


def _records(frame: pd.DataFrame, limit: int) -> list[dict[str, JsonValue]]:
    if frame.empty:
        return []
    readable = frame.rename(columns=snake_case)
    index_name = snake_case(frame.index.name) if frame.index.name else "key"
    return frame_to_records(readable, index_name=index_name, limit=limit).records  # type: ignore[return-value]


def register(server: MCPServer, context: ToolContext) -> None:
    @server.tool(title="Get events", annotations=READ_ONLY)
    def get_events(
        kind: Annotated[
            EventKind, Field(description="Calendar: earnings, ipo, economic or splits.")
        ] = "earnings",
        start: Annotated[
            date | None, Field(description="First day (YYYY-MM-DD); default today.")
        ] = None,
        end: Annotated[
            date | None, Field(description="Last day (YYYY-MM-DD); default start + 7 days.")
        ] = None,
        symbols: Annotated[
            list[str] | None,
            Field(
                max_length=10,
                description="Earnings calendars of up to 10 symbols instead of the market-wide "
                "list: next earnings date, EPS/revenue estimates, dividend dates, past surprises.",
            ),
        ] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Maximum calendar rows.")] = 50,
        response_format: ResponseFormatParam = "concise",
    ) -> EventsResult:
        """Upcoming events that move prices: earnings, IPOs, economic releases and splits.

        Without symbols it lists market-wide events in the date range (at most 92 days).
        With symbols it returns each one's earnings calendar and recent earnings surprises.
        """
        checked = require_symbols(symbols) if symbols else []
        today = utc_now().date()
        key = {
            "tool": "get_events",
            "kind": kind,
            "start": start,
            "end": end,
            "symbols": checked,
            "limit": limit,
            "today": today,
        }
        return context.answer(
            "events",
            key,
            lambda: build_events(
                context.gateway,
                kind,
                check_event_range(kind, start, end, bool(checked), today),
                checked,
                limit,
            ),
            response_format,
        )
