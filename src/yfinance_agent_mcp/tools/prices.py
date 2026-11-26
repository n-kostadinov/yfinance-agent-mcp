"""Price history with the indicators an agent needs, sized to fit the response budget."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Annotated, Literal

import pandas as pd
from mcp.server import MCPServer
from pydantic import Field

from yfinance_agent_mcp.errors import InvalidArgument
from yfinance_agent_mcp.gateway import MarketDataGateway, PriceHistory
from yfinance_agent_mcp.indicators import summarize_prices
from yfinance_agent_mcp.models import Bar, PriceHistoryResult, SymbolPrices
from yfinance_agent_mcp.shaping import budget_for, iso_utc, round_price, to_json_value
from yfinance_agent_mcp.tools.context import (
    READ_ONLY,
    ResponseFormatParam,
    Symbols10,
    ToolContext,
    for_each_symbol,
    require_symbols,
    utc_now,
)

Period = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
Interval = Literal[
    "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"
]
Mode = Literal["summary", "bars"]
INTRADAY = frozenset({"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"})

# Yahoo serves intraday bars for the last 60 days, and 1-minute bars for at most 7 days
# per request within the last 30 days.
_INTRADAY_DAYS = 60
_INTRADAY_PERIODS = ("1d", "5d", "1mo")
_MINUTE_DAYS, _MINUTE_WINDOW_DAYS = 7, 30
_MINUTE_PERIODS = ("1d", "5d")
# Approximate JSON sizes used to decide how many bars fit the budget.
_BAR_CHARS = 130
_SYMBOL_CHARS = {"summary": 1_300, "bars": 300}
_ENVELOPE_CHARS = 1_000


@dataclass(frozen=True)
class PriceRequest:
    """A range Yahoo can serve: either a period, or a start date with an optional end."""

    period: Period | None
    interval: Interval
    start: date | None
    end: date | None


def check_price_request(
    period: Period | None, interval: Interval, start: date | None, end: date | None, today: date
) -> PriceRequest:
    """Reject ranges Yahoo cannot serve, so no request is wasted on them."""
    if start is None and end is not None:
        raise InvalidArgument("end needs a start date; or give a period instead")
    if start is not None:
        period = None
        if start > (end or today):
            raise InvalidArgument(f"start {start} is after end {end or today}")
    if interval in INTRADAY:
        _check_intraday(period, interval, start, end, today)
    return PriceRequest(period=period, interval=interval, start=start, end=end)


def _check_intraday(
    period: Period | None, interval: Interval, start: date | None, end: date | None, today: date
) -> None:
    if interval == "1m":
        reason = f"1m bars cover at most {_MINUTE_DAYS} days per request"
        if start is None and period not in _MINUTE_PERIODS:
            raise InvalidArgument(reason, _MINUTE_PERIODS)
        too_long = start is not None and (end or today) - start > timedelta(days=_MINUTE_DAYS)
        too_old = start is not None and start < today - timedelta(days=_MINUTE_WINDOW_DAYS)
        if too_long or too_old:
            raise InvalidArgument(f"{reason}, within the last {_MINUTE_WINDOW_DAYS} days")
        return
    reason = f"{interval} bars only cover the last {_INTRADAY_DAYS} days; use interval 1d for more"
    if start is None and period not in _INTRADAY_PERIODS:
        raise InvalidArgument(reason, _INTRADAY_PERIODS)
    if start is not None and start < today - timedelta(days=_INTRADAY_DAYS):
        raise InvalidArgument(reason)


def build_price_history(
    gateway: MarketDataGateway,
    symbols: Sequence[str],
    request: PriceRequest,
    mode: Mode,
    bars_wanted: int,
    budget: int,
) -> PriceHistoryResult:
    histories, errors = for_each_symbol(
        symbols,
        lambda symbol: gateway.history(
            symbol,
            period=request.period,
            interval=request.interval,
            start=request.start,
            end=request.end,
        ),
    )
    per_symbol = (budget - _ENVELOPE_CHARS) // max(1, len(histories)) - _SYMBOL_CHARS[mode]
    bar_limit = max(1, min(bars_wanted, per_symbol // _BAR_CHARS))
    warnings = []
    if bar_limit < bars_wanted:
        warnings.append(
            f"Returned the last {bar_limit} of the {bars_wanted} bars asked for per symbol "
            "to fit the response budget; ask for fewer symbols or use response_format='detailed'."
        )
    return PriceHistoryResult(
        as_of=utc_now(),
        period=request.period,
        start=request.start.isoformat() if request.start else None,
        end=request.end.isoformat() if request.end else None,
        interval=request.interval,
        mode=mode,
        prices=[_symbol_prices(h, request.interval, mode, bar_limit) for h in histories],
        errors=errors,
        warnings=warnings,
    )


def _symbol_prices(
    history: PriceHistory, interval: str, mode: Mode, bar_limit: int
) -> SymbolPrices:
    bars = history.bars
    recent = bars.iloc[-bar_limit:]
    return SymbolPrices(
        symbol=history.meta.symbol,
        currency=history.meta.currency,
        exchange=history.meta.exchange,
        interval=interval,
        bar_count=len(bars),
        first_bar_time=iso_utc(bars.index[0]),
        last_bar_time=iso_utc(bars.index[-1]),
        summary=summarize_prices(bars) if mode == "summary" else None,
        bars=[
            _bar(when, row)
            for when, row in zip(recent.index, recent.to_dict("records"), strict=True)
        ],
    )


def _bar(when: pd.Timestamp, row: dict[str, object]) -> Bar:
    def price(column: str) -> float | None:
        value = to_json_value(row[column])
        return round_price(value) if isinstance(value, int | float) else None

    volume = to_json_value(row["volume"])
    return Bar(
        time=iso_utc(when) or "",
        open=price("open"),
        high=price("high"),
        low=price("low"),
        close=price("close"),
        volume=float(volume) if isinstance(volume, int | float) else None,
    )


def register(server: MCPServer, context: ToolContext) -> None:
    @server.tool(title="Get price history", annotations=READ_ONLY)
    def get_price_history(
        symbols: Symbols10,
        period: Annotated[
            Period, Field(description="How far back to look; ignored when start is given.")
        ] = "6mo",
        interval: Annotated[
            Interval,
            Field(description="Bar length. Intraday bars cover the last 60 days (1m: 7 days)."),
        ] = "1d",
        start: Annotated[
            date | None, Field(description="First day (YYYY-MM-DD); overrides period.")
        ] = None,
        end: Annotated[
            date | None, Field(description="Day after the last bar (YYYY-MM-DD); needs start.")
        ] = None,
        mode: Annotated[
            Mode,
            Field(
                description="'summary' adds returns, moving averages, RSI, ATR, 52-week range "
                "and volume ratio to the last bars; 'bars' returns bars only."
            ),
        ] = "summary",
        bars: Annotated[
            int, Field(ge=1, le=500, description="How many of the most recent bars to return.")
        ] = 20,
        response_format: ResponseFormatParam = "concise",
    ) -> PriceHistoryResult:
        """Price history for up to 10 symbols, with ready-made indicators.

        The summary saves you computing trend and momentum yourself: changes over 1d to 1y
        and YTD, SMA 20/50/200, RSI 14, ATR 14, 52-week range and volume vs. average.
        Prices are adjusted for splits and dividends.
        """
        checked = require_symbols(symbols)
        category = "history_intraday" if interval in INTRADAY else "history_daily"
        key = {
            "tool": "get_price_history",
            "symbols": checked,
            "period": period,
            "interval": interval,
            "start": start,
            "end": end,
            "mode": mode,
            "bars": bars,
        }
        return context.answer(
            category,
            key,
            lambda: build_price_history(
                context.gateway,
                checked,
                check_price_request(period, interval, start, end, utc_now().date()),
                mode,
                bars,
                budget_for(response_format),
            ),
            response_format,
        )
