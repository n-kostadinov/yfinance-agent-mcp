"""In-memory stand-in for the yfinance gateway, used by unit and in-process integration tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import Any, cast

import pandas as pd

from yfinance_agent_mcp.errors import DomainError, NotFound
from yfinance_agent_mcp.gateway import (
    AnalystData,
    ChartMeta,
    OptionChain,
    PriceHistory,
    ScreenPage,
    SectorData,
    TickerEvents,
)
from yfinance_agent_mcp.models import (
    KeyStats,
    MarketIndex,
    MarketStatus,
    NewsItem,
    Quote,
    SymbolMatch,
)


class FakeStream:
    """Stands in for Yahoo's live feed: emits canned ticks for subscribed symbols."""

    def __init__(self, ticks: Mapping[str, dict[str, Any]] | None = None) -> None:
        self.ticks = dict(ticks or {})
        self.subscribed: set[str] = set()
        self.closed = False
        self.listen_error: Exception | None = None
        self._handler: Callable[[dict[str, Any]], Any] | None = None

    async def subscribe(self, symbols: list[str]) -> None:
        self.subscribed |= set(symbols)
        self._emit(symbols)

    async def unsubscribe(self, symbols: list[str]) -> None:
        self.subscribed -= set(symbols)

    async def listen(self, message_handler: Callable[[dict[str, Any]], Any]) -> None:
        self._handler = message_handler
        self._emit(sorted(self.subscribed))
        if self.listen_error is not None:
            raise self.listen_error
        await asyncio.Event().wait()  # until cancelled, like a real feed

    async def close(self) -> None:
        self.closed = True

    def push(self, message: dict[str, Any]) -> None:
        assert self._handler is not None, "push() needs a running listen()"
        self._handler(message)

    def _emit(self, symbols: list[str]) -> None:
        if self._handler is None:
            return
        for symbol in symbols:
            if symbol in self.ticks:
                self._handler(self.ticks[symbol])


class FakeGateway:
    """Returns canned data per operation; ``fail`` makes an operation raise a DomainError.

    ``fail_symbol`` makes one symbol of a per-symbol operation raise.
    """

    def __init__(self) -> None:
        self.symbol_matches: dict[str, list[SymbolMatch]] = {}
        self.lookups: dict[tuple[str, str], list[SymbolMatch]] = {}
        self.histories: dict[str, PriceHistory] = {}
        self.quotes: dict[str, Quote] = {}
        self.markets: dict[str, tuple[MarketStatus | None, list[MarketIndex]]] = {}
        self.ticker_articles: dict[str, list[NewsItem]] = {}
        self.search_articles: dict[str, list[NewsItem]] = {}
        self.screens: dict[str, ScreenPage] = {}
        self.sectors: dict[tuple[str, str], SectorData] = {}
        self.calendars: dict[str, pd.DataFrame] = {}
        self.ticker_calendars: dict[str, TickerEvents] = {}
        self.statements: dict[tuple[str, str, str], pd.DataFrame] = {}
        self.valuations: dict[str, pd.DataFrame] = {}
        self.stats: dict[str, KeyStats] = {}
        self.analysts: dict[str, AnalystData] = {}
        self.expirations: dict[str, list[str]] = {}
        self.chains: dict[tuple[str, str], OptionChain] = {}
        self.datasets: dict[tuple[str, str], object] = {}
        self.streams: list[FakeStream] = []
        self.live_ticks: dict[str, dict[str, Any]] = {}
        self.failures: dict[str, DomainError] = {}
        self.symbol_failures: dict[str, DomainError] = {}
        self.failure_for_everything: DomainError | None = None
        self.calls: list[str] = []

    def fail(self, operation: str, error: DomainError) -> None:
        self.failures[operation] = error

    def fail_everything(self, error: DomainError) -> None:
        self.failure_for_everything = error

    def fail_symbol(self, symbol: str, error: DomainError) -> None:
        self.symbol_failures[symbol] = error

    def search_quotes(self, query: str, limit: int) -> list[SymbolMatch]:
        self._enter("search_quotes")
        return self.symbol_matches.get(query, [])[:limit]

    def lookup(self, query: str, kind: str, limit: int) -> list[SymbolMatch]:
        self._enter("lookup")
        return self.lookups.get((query, kind), [])[:limit]

    def quote(self, symbol: str, *, details: bool = False) -> Quote:
        self._enter("quote", symbol)
        if symbol not in self.quotes:
            raise NotFound(f"${symbol}: possibly delisted; no price data found")
        quote = self.quotes[symbol]
        if details:
            return quote
        return quote.model_copy(update={"details": None, "delay_min": None, "quote_source": None})

    def market(self, region: str) -> tuple[MarketStatus | None, list[MarketIndex]]:
        self._enter("market")
        return self.markets.get(region, (None, []))

    def ticker_news(self, symbol: str, count: int, tab: str) -> list[NewsItem]:
        self._enter("ticker_news", symbol)
        return self.ticker_articles.get(symbol, [])[:count]

    def search_news(self, query: str, count: int) -> list[NewsItem]:
        self._enter("search_news")
        return self.search_articles.get(query, [])[:count]

    def screen(
        self,
        *,
        preset: str | None,
        query: Mapping[str, Any] | None,
        security_type: str,
        sort_field: str | None,
        ascending: bool,
        count: int,
    ) -> ScreenPage:
        self._enter("screen")
        return self.screens.get(preset or "custom", ScreenPage(title=None, total=0, rows=[]))

    def sector_industry(self, kind: str, key: str) -> SectorData:
        self._enter("sector_industry")
        if (kind, key) not in self.sectors:
            raise NotFound(f"Yahoo Finance has no such item (HTTP 404): {kind} {key}")
        return self.sectors[(kind, key)]

    def calendar_events(self, kind: str, start: date, end: date, limit: int) -> pd.DataFrame:
        self._enter("calendar_events")
        return self.calendars.get(kind, pd.DataFrame()).head(limit)

    def ticker_events(self, symbol: str, earnings_limit: int) -> TickerEvents:
        self._enter("ticker_events", symbol)
        if symbol not in self.ticker_calendars:
            raise NotFound(f"${symbol}: no calendar")
        return self.ticker_calendars[symbol]

    def statement(self, symbol: str, statement: str, freq: str) -> pd.DataFrame:
        self._enter("statement", symbol)
        if (symbol, statement, freq) not in self.statements:
            raise NotFound(f"Yahoo has no {freq} {statement} statement for {symbol}")
        return self.statements[(symbol, statement, freq)]

    def valuation(self, symbol: str) -> pd.DataFrame:
        self._enter("valuation", symbol)
        if symbol not in self.valuations:
            raise NotFound(f"Yahoo has no valuation measures for {symbol}")
        return self.valuations[symbol]

    def key_stats(self, symbol: str) -> KeyStats:
        self._enter("key_stats", symbol)
        return self.stats.get(symbol, KeyStats())

    def analyst(self, symbol: str) -> AnalystData:
        self._enter("analyst", symbol)
        if symbol not in self.analysts:
            raise NotFound(f"${symbol}: no analyst coverage")
        return self.analysts[symbol]

    def option_expirations(self, symbol: str) -> list[str]:
        self._enter("option_expirations", symbol)
        return self.expirations.get(symbol, [])

    def option_chain(self, symbol: str, expiry: str) -> OptionChain:
        self._enter("option_chain", symbol)
        return self.chains[(symbol, expiry)]

    def ticker_dataset(self, symbol: str, dataset: str) -> object:
        self._enter("ticker_dataset", symbol)
        if (symbol, dataset) not in self.datasets:
            raise NotFound(f"Yahoo has no {dataset} for {symbol}")
        return self.datasets[(symbol, dataset)]

    def open_live_stream(self) -> FakeStream:
        self._enter("open_live_stream")
        stream = FakeStream(self.live_ticks)
        self.streams.append(stream)
        return stream

    def history(
        self,
        symbol: str,
        *,
        period: str | None = None,
        interval: str = "1d",
        start: date | None = None,
        end: date | None = None,
    ) -> PriceHistory:
        self._enter("history", symbol)
        if symbol not in self.histories:
            raise NotFound(f"${symbol}: possibly delisted; no price data found")
        return self.histories[symbol]

    def _enter(self, operation: str, symbol: str | None = None) -> None:
        self.calls.append(operation)
        if self.failure_for_everything is not None:
            raise self.failure_for_everything
        if operation in self.failures:
            raise self.failures[operation]
        if symbol is not None and symbol in self.symbol_failures:
            raise self.symbol_failures[symbol]


def make_history(
    symbol: str,
    closes: list[float],
    *,
    start: str = "2026-01-02",
    freq: str = "D",
    volume: float = 1_000_000.0,
    meta: ChartMeta | None = None,
) -> PriceHistory:
    """A price history whose bars close at ``closes`` (high/low 1% around the close)."""
    index = pd.date_range(start, periods=len(closes), freq=freq, tz=UTC)
    bars = pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [volume] * len(closes),
        },
        index=index,
    )
    last_time = (
        cast(pd.Timestamp, index[-1]).to_pydatetime()
        if len(index)
        else datetime(2026, 1, 2, tzinfo=UTC)
    )
    return PriceHistory(
        bars=bars,
        meta=meta
        or ChartMeta(
            symbol=symbol,
            name=f"{symbol} Inc.",
            currency="USD",
            exchange="NasdaqGS",
            instrument_type="EQUITY",
            timezone="America/New_York",
            price=closes[-1] if closes else None,
            market_time=last_time,
            session="REGULAR",
        ),
    )
