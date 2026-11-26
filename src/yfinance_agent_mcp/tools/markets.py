"""Find symbols, quote them, and see how the market is doing."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal

from mcp.server import MCPServer
from pydantic import Field

from yfinance_agent_mcp.gateway import MarketDataGateway
from yfinance_agent_mcp.models import MarketOverview, QuotesResult, SymbolSearchResult
from yfinance_agent_mcp.tools.context import (
    READ_ONLY,
    ResponseFormatParam,
    Symbols25,
    ToolContext,
    for_each_symbol,
    require_symbols,
    utc_now,
)

SymbolKind = Literal[
    "any", "equity", "etf", "mutualfund", "index", "future", "currency", "cryptocurrency"
]
Region = Literal[
    "US", "GB", "ASIA", "EUROPE", "RATES", "COMMODITIES", "CURRENCIES", "CRYPTOCURRENCIES"
]
_DETAILS_HINT = (
    "delay_min and quote_source are filled only with include_details=true (one more Yahoo "
    "request per symbol); market_state is derived from the exchange's trading hours."
)


def build_symbol_search(
    gateway: MarketDataGateway, query: str, kind: SymbolKind, limit: int
) -> SymbolSearchResult:
    if kind == "any":
        matches = gateway.search_quotes(query, limit)
    else:
        matches = gateway.lookup(query, kind, limit)
    warnings = (
        []
        if matches
        else [f"No matches for {query!r}; try a company name, a ticker or another kind."]
    )
    return SymbolSearchResult(
        as_of=utc_now(), query=query, kind=kind, matches=matches, warnings=warnings
    )


def build_quotes(
    gateway: MarketDataGateway, symbols: Sequence[str], include_details: bool
) -> QuotesResult:
    quotes, errors = for_each_symbol(
        symbols, lambda symbol: gateway.quote(symbol, details=include_details)
    )
    warnings = [] if include_details else [_DETAILS_HINT]
    delayed = [q for q in quotes if q.delay_min]
    if delayed:
        longest = max(q.delay_min or 0 for q in delayed)
        names = ", ".join(q.symbol for q in delayed)
        warnings.append(f"Delayed by up to {longest} min: {names}.")
    return QuotesResult(as_of=utc_now(), quotes=quotes, errors=errors, warnings=warnings)


def build_market_overview(gateway: MarketDataGateway, region: Region) -> MarketOverview:
    status, indices = gateway.market(region)
    delayed = [index for index in indices if index.delay_min]
    warnings = []
    if delayed:
        longest = max(index.delay_min or 0 for index in delayed)
        warnings.append(
            f"{len(delayed)} of {len(indices)} prices are delayed by up to {longest} min."
        )
    return MarketOverview(
        as_of=utc_now(), region=region, status=status, indices=indices, warnings=warnings
    )


def register(server: MCPServer, context: ToolContext) -> None:
    @server.tool(title="Search symbols", annotations=READ_ONLY)
    def search_symbols(
        query: Annotated[
            str,
            Field(
                min_length=1,
                max_length=100,
                description="Company name, ticker or keyword, e.g. 'nvidia', 'SAP' or 'gold'.",
            ),
        ],
        kind: Annotated[
            SymbolKind, Field(description="Narrow to one kind of security; 'any' searches all.")
        ] = "any",
        limit: Annotated[int, Field(ge=1, le=10, description="Maximum matches.")] = 10,
        response_format: ResponseFormatParam = "concise",
    ) -> SymbolSearchResult:
        """Find Yahoo Finance symbols for a company name, ticker or keyword.

        Use it first when you only know a name: the other tools need exact Yahoo symbols
        such as AAPL, SAP.DE, BTC-USD or ^GSPC.
        """
        text = query.strip()
        return context.answer(
            "search",
            {"tool": "search_symbols", "query": text.lower(), "kind": kind, "limit": limit},
            lambda: build_symbol_search(context.gateway, text, kind, limit),
            response_format,
        )

    @server.tool(title="Get quotes", annotations=READ_ONLY)
    def get_quotes(
        symbols: Symbols25,
        include_details: Annotated[
            bool,
            Field(
                description="Add market cap, P/E, dividend yield, bid/ask, Yahoo's market state, "
                "quote source and delay (one more Yahoo request per symbol)."
            ),
        ] = False,
        response_format: ResponseFormatParam = "concise",
    ) -> QuotesResult:
        """Latest price, daily change, day range, volume and 52-week range for up to 25 symbols.

        Symbols without data are listed in `errors` instead of failing the whole call.
        Check `market_time` and `delay_min` before acting on a price.
        """
        checked = require_symbols(symbols)
        return context.answer(
            "quotes",
            {"tool": "get_quotes", "symbols": checked, "details": include_details},
            lambda: build_quotes(context.gateway, checked, include_details),
            response_format,
        )

    @server.tool(title="Get market overview", annotations=READ_ONLY)
    def get_market_overview(
        region: Annotated[Region, Field(description="Market region.")] = "US",
        response_format: ResponseFormatParam = "concise",
    ) -> MarketOverview:
        """Whether a region's market is open, and its headline indices, futures or rates."""
        return context.answer(
            "market",
            {"tool": "get_market_overview", "region": region},
            lambda: build_market_overview(context.gateway, region),
            response_format,
        )
