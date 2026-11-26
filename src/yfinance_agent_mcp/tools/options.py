"""Option chains around the current price, for one symbol and expiration."""

from __future__ import annotations

from typing import Annotated

import pandas as pd
from mcp.server import MCPServer
from pydantic import Field, JsonValue

from yfinance_agent_mcp.errors import InvalidArgument, NotFound
from yfinance_agent_mcp.gateway import MarketDataGateway
from yfinance_agent_mcp.models import OptionsResult
from yfinance_agent_mcp.shaping import frame_to_records, to_json_value
from yfinance_agent_mcp.tools.context import (
    READ_ONLY,
    ResponseFormatParam,
    SymbolParam,
    ToolContext,
    require_symbols,
    utc_now,
)

# Yahoo column -> key in the answer, for the columns worth an agent's tokens.
_COLUMNS = {
    "contractSymbol": "contract_symbol",
    "strike": "strike",
    "lastPrice": "last_price",
    "bid": "bid",
    "ask": "ask",
    "percentChange": "change_pct",
    "volume": "volume",
    "openInterest": "open_interest",
    "impliedVolatility": "implied_volatility",
    "inTheMoney": "in_the_money",
    "lastTradeDate": "last_trade_date",
}


def build_options(
    gateway: MarketDataGateway, symbol: str, expiry: str | None, strikes_each_side: int
) -> OptionsResult:
    expirations = gateway.option_expirations(symbol)
    if not expirations:
        raise NotFound(f"{symbol} has no listed options on Yahoo Finance")
    chosen = expiry or expirations[0]
    if chosen not in expirations:
        raise InvalidArgument(f"{symbol} has no options expiring {chosen}", expirations)
    chain = gateway.option_chain(symbol, chosen)
    spot = to_json_value(chain.underlying.get("regularMarketPrice"))
    price = float(spot) if isinstance(spot, int | float) else None
    return OptionsResult(
        as_of=utc_now(),
        symbol=symbol,
        expiry=chosen,
        expirations=expirations,
        underlying_price=price,
        calls=_around(chain.calls, price, strikes_each_side),
        puts=_around(chain.puts, price, strikes_each_side),
    )


def _around(side: pd.DataFrame, price: float | None, each_side: int) -> list[dict[str, JsonValue]]:
    """The ``each_side`` strikes below the price and the ``each_side`` at or above it."""
    if side.empty:
        return []
    ordered = side.sort_values("strike")
    strikes = ordered["strike"].to_numpy(dtype=float)
    below = int((strikes < price).sum()) if price is not None else len(ordered) // 2
    window = ordered.iloc[max(0, below - each_side) : below + each_side]
    present = [column for column in _COLUMNS if column in window.columns]
    readable = window.loc[:, present].rename(columns=_COLUMNS)
    return frame_to_records(readable).records  # type: ignore[return-value]


def register(server: MCPServer, context: ToolContext) -> None:
    @server.tool(title="Get options", annotations=READ_ONLY)
    def get_options(
        symbol: SymbolParam,
        expiry: Annotated[
            str | None,
            Field(
                pattern=r"^\d{4}-\d{2}-\d{2}$",
                description="Expiration date (YYYY-MM-DD); default the nearest.",
            ),
        ] = None,
        strikes_each_side: Annotated[
            int, Field(ge=1, le=25, description="Strikes to show below and above the price.")
        ] = 10,
        response_format: ResponseFormatParam = "concise",
    ) -> OptionsResult:
        """Calls and puts around the current price for one expiration, plus every expiry.

        Each contract has last price, bid/ask, change %, volume, open interest, implied
        volatility and whether it is in the money.
        """
        checked = require_symbols([symbol])[0]
        key = {
            "tool": "get_options",
            "symbol": checked,
            "expiry": expiry,
            "strikes_each_side": strikes_each_side,
        }
        return context.answer(
            "options",
            key,
            lambda: build_options(context.gateway, checked, expiry, strikes_each_side),
            response_format,
        )
