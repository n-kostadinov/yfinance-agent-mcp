"""What every tool shares: the gateway, the result cache, and one way to answer a call."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cached_property
from typing import Annotated, TypeVar

from mcp.types import ToolAnnotations
from pydantic import Field

from yfinance_agent_mcp.cache import TtlCache
from yfinance_agent_mcp.errors import DomainError, InvalidArgument, RateLimited
from yfinance_agent_mcp.gateway import MarketDataGateway
from yfinance_agent_mcp.live import LiveQuotes
from yfinance_agent_mcp.models import SymbolError
from yfinance_agent_mcp.shaping import EnvelopeT, ResponseFormat, budget_for, fit_to_budget

T = TypeVar("T")

# Every tool only reads public market data from Yahoo Finance (an open world).
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)

ResponseFormatParam = Annotated[
    ResponseFormat,
    Field(description="'concise' (default; up to 20,000 characters) or 'detailed' (up to 80,000)."),
]
_SYMBOLS_DESCRIPTION = (
    "Yahoo Finance symbols, e.g. ['AAPL', 'SAP.DE', 'BTC-USD', '^GSPC', 'EURUSD=X']."
)
Symbols25 = Annotated[
    list[str], Field(min_length=1, max_length=25, description=f"Up to 25 {_SYMBOLS_DESCRIPTION}")
]
Symbols10 = Annotated[
    list[str], Field(min_length=1, max_length=10, description=f"Up to 10 {_SYMBOLS_DESCRIPTION}")
]
SymbolParam = Annotated[
    str, Field(min_length=1, max_length=24, description="One Yahoo Finance symbol, e.g. AAPL.")
]
_SYMBOL = re.compile(r"[A-Z0-9^][A-Z0-9.\-=^&_]{0,23}")


def utc_now() -> datetime:
    return datetime.now(UTC)


def require_symbols(symbols: Sequence[str]) -> list[str]:
    """Upper-case, de-duplicate and check symbols; bad input becomes a tool error."""
    normalized = list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))
    invalid = [symbol for symbol in normalized if not _SYMBOL.fullmatch(symbol)]
    if invalid or not normalized:
        problem = f"not Yahoo Finance symbols: {', '.join(invalid)}" if invalid else "no symbols"
        message = f"{problem}; use search_symbols to find the right symbol"
        raise InvalidArgument(message).to_tool_error()
    return normalized


def for_each_symbol(
    symbols: Sequence[str], fetch: Callable[[str], T]
) -> tuple[list[T], list[SymbolError]]:
    """Fetch every symbol and collect failures per symbol; raise only if none succeeded.

    After a rate limit the remaining symbols are reported as skipped, because more requests
    would only extend Yahoo's block.
    """
    results: list[T] = []
    errors: list[SymbolError] = []
    first_error: DomainError | None = None
    for position, symbol in enumerate(symbols):
        try:
            results.append(fetch(symbol))
        except RateLimited as error:
            first_error = first_error or error
            errors.extend(_symbol_error(skipped, error) for skipped in symbols[position:])
            break
        except DomainError as error:
            first_error = first_error or error
            errors.append(_symbol_error(symbol, error))
    if not results and first_error is not None:
        raise first_error
    return results, errors


def _symbol_error(symbol: str, error: DomainError) -> SymbolError:
    return SymbolError(symbol=symbol, error=error.code, message=error.message)


@dataclass(frozen=True)
class ToolContext:
    gateway: MarketDataGateway
    cache: TtlCache

    @cached_property
    def live(self) -> LiveQuotes:
        """The shared live price stream; it connects on first use."""
        return LiveQuotes(self.gateway.open_live_stream)

    def answer(
        self,
        category: str,
        key_args: Mapping[str, object],
        build: Callable[[], EnvelopeT],
        response_format: ResponseFormat,
    ) -> EnvelopeT:
        """Serve a cached result or build a new one that fits the response budget.

        ``DomainError``s become MCP tool errors, so the model reads ``<code>: <advice>``.
        """
        budget = budget_for(response_format)
        try:
            return self.cache.get_or_compute(
                category,
                {**key_args, "response_format": response_format},
                lambda: fit_to_budget(build(), budget),
            )
        except DomainError as error:
            raise error.to_tool_error() from error
