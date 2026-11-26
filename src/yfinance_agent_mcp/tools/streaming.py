"""Live prices from Yahoo's streaming feed."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Annotated

from mcp.server import MCPServer
from pydantic import Field

from yfinance_agent_mcp.errors import DomainError
from yfinance_agent_mcp.live import Tick
from yfinance_agent_mcp.models import LiveQuotesResult, LiveTick
from yfinance_agent_mcp.shaping import budget_for, fit_to_budget, iso_utc
from yfinance_agent_mcp.tools.context import (
    READ_ONLY,
    ResponseFormatParam,
    Symbols25,
    ToolContext,
    require_symbols,
    utc_now,
)


def build_live_quotes(
    ticks: Mapping[str, Tick], missing: Sequence[str], now: datetime, wait_seconds: float
) -> LiveQuotesResult:
    result = LiveQuotesResult(
        as_of=now,
        ticks=[_live_tick(symbol, tick, now) for symbol, tick in ticks.items()],
        missing=list(missing),
    )
    if missing:
        result.warnings.append(
            f"No tick within {wait_seconds:g} s for {', '.join(missing)}: the market may be "
            "closed or the symbol illiquid or unknown; get_quotes has the last price."
        )
    return result


def _live_tick(symbol: str, tick: Tick, now: datetime) -> LiveTick:
    message = tick.message
    return LiveTick(
        symbol=symbol,
        price=_number(message.get("price")),
        change_pct=_number(message.get("change_percent")),
        day_volume=_number(message.get("day_volume")),
        market_hours=str(message["market_hours"]) if message.get("market_hours") else None,
        exchange_time=_exchange_time(message.get("time")),
        received_at=iso_utc(tick.received_at) or "",
        age_seconds=round((now - tick.received_at).total_seconds(), 1),
    )


def _number(value: object) -> float | None:
    """The feed sends 64-bit integers as strings; accept both."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _exchange_time(value: object) -> str | None:
    milliseconds = _number(value)
    if milliseconds is None:
        return None
    return iso_utc(datetime.fromtimestamp(milliseconds / 1_000, UTC))


def register(server: MCPServer, context: ToolContext) -> None:
    @server.tool(title="Get live quotes", annotations=READ_ONLY)
    async def get_live_quotes(
        symbols: Symbols25,
        wait_seconds: Annotated[
            float,
            Field(ge=0, le=10, description="How long to wait for symbols without a tick yet."),
        ] = 3.0,
        response_format: ResponseFormatParam = "concise",
    ) -> LiveQuotesResult:
        """The price right now from Yahoo's streaming feed, for up to 25 symbols.

        The first call subscribes and waits for ticks; later calls answer at once with the
        latest tick and its age. Quiet symbols (market closed) are listed in `missing`.
        """
        checked = require_symbols(symbols)
        try:
            ticks, missing = await context.live.latest(checked, wait_seconds)
        except DomainError as error:
            raise error.to_tool_error() from error
        result = build_live_quotes(ticks, missing, utc_now(), wait_seconds)
        return fit_to_budget(result, budget_for(response_format))
