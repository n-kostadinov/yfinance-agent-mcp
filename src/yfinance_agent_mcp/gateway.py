"""The only module that imports yfinance; tools reach Yahoo through ``MarketDataGateway``.

``YFinanceGateway`` hides yfinance's process-wide quirks behind that port:

- it configures yfinance once: raise errors instead of returning empty data, retry transient
  network errors, keep its SQLite caches in the server's cache directory, apply the locale;
- every HTTP request goes through one rate-limited ``curl_cffi`` session;
- each call builds new yfinance objects and clears yfinance's never-expiring internal cache,
  so the server's own TTL cache alone decides how fresh results are;
- yfinance exceptions become the project's ``DomainError`` types.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

import pandas as pd
import yfinance as yf
from curl_cffi import requests as curl_requests
from yfinance import EquityQuery, ETFQuery, FundQuery
from yfinance import exceptions as yf_errors
from yfinance.data import YfData

from yfinance_agent_mcp.config import Settings
from yfinance_agent_mcp.errors import (
    DomainError,
    InvalidArgument,
    NotFound,
    RateLimited,
    UpstreamError,
)
from yfinance_agent_mcp.models import (
    KeyStats,
    MarketIndex,
    MarketStatus,
    NewsItem,
    Quote,
    QuoteDetails,
    ScreenRow,
    SymbolMatch,
    UntrustedText,
)
from yfinance_agent_mcp.ratelimit import CooldownActive, RateLimiter
from yfinance_agent_mcp.shaping import iso_utc

logger = logging.getLogger(__name__)

BAR_COLUMNS = ("open", "high", "low", "close", "volume")
# Security kinds Lookup can search, mapped to its get_<method>() names.
LOOKUP_KINDS = {
    "equity": "stock",
    "etf": "etf",
    "mutualfund": "mutualfund",
    "index": "index",
    "future": "future",
    "currency": "currency",
    "cryptocurrency": "cryptocurrency",
}
SCREEN_OPERATORS = ("and", "or", "eq", "gt", "lt", "gte", "lte", "btwn", "is-in")
SCREENER_PRESETS = tuple(yf.PREDEFINED_SCREENER_QUERIES)
_QUERY_CLASSES = {"equity": EquityQuery, "fund": FundQuery, "etf": ETFQuery}
# KeyStats field -> Yahoo quote-summary key.
_KEY_STATS = {
    "market_cap": "marketCap",
    "enterprise_value": "enterpriseValue",
    "trailing_pe": "trailingPE",
    "forward_pe": "forwardPE",
    "peg_ratio": "trailingPegRatio",
    "price_to_book": "priceToBook",
    "price_to_sales": "priceToSalesTrailing12Months",
    "ev_to_revenue": "enterpriseToRevenue",
    "ev_to_ebitda": "enterpriseToEbitda",
    "profit_margin": "profitMargins",
    "gross_margin": "grossMargins",
    "operating_margin": "operatingMargins",
    "return_on_equity": "returnOnEquity",
    "return_on_assets": "returnOnAssets",
    "revenue_growth": "revenueGrowth",
    "earnings_growth": "earningsGrowth",
    "debt_to_equity": "debtToEquity",
    "current_ratio": "currentRatio",
    "quick_ratio": "quickRatio",
    "total_cash": "totalCash",
    "total_debt": "totalDebt",
    "free_cash_flow": "freeCashflow",
    "dividend_yield_pct": "dividendYield",
    "payout_ratio": "payoutRatio",
    "beta": "beta",
    "shares_outstanding": "sharesOutstanding",
    "float_shares": "floatShares",
    "short_percent_of_float": "shortPercentOfFloat",
    "held_by_insiders": "heldPercentInsiders",
    "held_by_institutions": "heldPercentInstitutions",
}
# Dataset name -> attribute path on yfinance.Ticker. The other tools cover prices, quotes,
# news, statements, analysts, calendars and options; these are the long tail.
TICKER_DATASETS: dict[str, tuple[str, ...]] = {
    "info": ("info",),
    "major_holders": ("major_holders",),
    "institutional_holders": ("institutional_holders",),
    "mutualfund_holders": ("mutualfund_holders",),
    "insider_purchases": ("insider_purchases",),
    "insider_transactions": ("insider_transactions",),
    "insider_roster_holders": ("insider_roster_holders",),
    "dividends": ("dividends",),
    "splits": ("splits",),
    "capital_gains": ("capital_gains",),
    "actions": ("actions",),
    "isin": ("isin",),
    "sustainability": ("sustainability",),
    "sec_filings": ("sec_filings",),
    "earnings_history": ("earnings_history",),
    "history_metadata": ("history_metadata",),
    "fund_description": ("funds_data", "description"),
    "fund_overview": ("funds_data", "fund_overview"),
    "fund_operations": ("funds_data", "fund_operations"),
    "fund_asset_classes": ("funds_data", "asset_classes"),
    "fund_top_holdings": ("funds_data", "top_holdings"),
    "fund_equity_holdings": ("funds_data", "equity_holdings"),
    "fund_bond_holdings": ("funds_data", "bond_holdings"),
    "fund_bond_ratings": ("funds_data", "bond_ratings"),
    "fund_sector_weightings": ("funds_data", "sector_weightings"),
}
MARKET_REGIONS = (
    "US",
    "GB",
    "ASIA",
    "EUROPE",
    "RATES",
    "COMMODITIES",
    "CURRENCIES",
    "CRYPTOCURRENCIES",
)


@dataclass(frozen=True)
class ChartMeta:
    """Quote fields Yahoo returns with every price history."""

    symbol: str
    name: str | None = None
    currency: str | None = None
    exchange: str | None = None
    instrument_type: str | None = None
    timezone: str | None = None
    price: float | None = None
    change_pct: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    volume: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    market_time: datetime | None = None
    session: str | None = None  # PRE, REGULAR, POST or CLOSED at fetch time


@dataclass(frozen=True)
class ScreenPage:
    title: str | None
    total: int | None
    rows: list[ScreenRow]


@dataclass(frozen=True)
class SectorData:
    """A sector or industry: overview fields, ranked tables, and fund lists (symbol -> name)."""

    kind: str
    key: str
    name: str | None
    sector_key: str | None
    sector_name: str | None
    overview: Mapping[str, Any]
    tables: Mapping[str, pd.DataFrame]
    funds: Mapping[str, Mapping[str, str]]


@dataclass(frozen=True)
class TickerEvents:
    """A symbol's calendar (earnings and dividend dates, estimates) and its earnings history."""

    calendar: Mapping[str, Any]
    earnings_dates: pd.DataFrame


@dataclass(frozen=True)
class AnalystData:
    """Analyst tables as yfinance returns them; any of them may be missing for a symbol."""

    price_targets: Mapping[str, Any]
    recommendations: pd.DataFrame | None
    rating_changes: pd.DataFrame | None
    earnings_estimate: pd.DataFrame | None
    revenue_estimate: pd.DataFrame | None
    eps_trend: pd.DataFrame | None
    eps_revisions: pd.DataFrame | None
    growth_estimates: pd.DataFrame | None


@dataclass(frozen=True)
class OptionChain:
    """Calls and puts of one expiration, plus the underlying's quote fields."""

    calls: pd.DataFrame
    puts: pd.DataFrame
    underlying: Mapping[str, Any]


@dataclass(frozen=True)
class PriceHistory:
    """Bars with ``BAR_COLUMNS`` on an ascending UTC index, plus the chart's quote fields."""

    bars: pd.DataFrame
    meta: ChartMeta


class LiveStream(Protocol):
    """A connection to Yahoo's live price feed (yfinance's AsyncWebSocket fits this)."""

    async def subscribe(self, symbols: list[str]) -> None: ...

    async def unsubscribe(self, symbols: list[str]) -> None: ...

    async def listen(self, message_handler: Callable[[dict[str, Any]], Any]) -> None: ...

    async def close(self) -> None: ...


class MarketDataGateway(Protocol):
    """What the tools need from Yahoo Finance, in the project's own data shapes."""

    def search_quotes(self, query: str, limit: int) -> list[SymbolMatch]: ...

    def lookup(self, query: str, kind: str, limit: int) -> list[SymbolMatch]: ...

    def history(
        self,
        symbol: str,
        *,
        period: str | None = None,
        interval: str = "1d",
        start: date | None = None,
        end: date | None = None,
    ) -> PriceHistory: ...

    def quote(self, symbol: str, *, details: bool = False) -> Quote: ...

    def market(self, region: str) -> tuple[MarketStatus | None, list[MarketIndex]]: ...

    def ticker_news(self, symbol: str, count: int, tab: str) -> list[NewsItem]: ...

    def search_news(self, query: str, count: int) -> list[NewsItem]: ...

    def screen(
        self,
        *,
        preset: str | None,
        query: Mapping[str, Any] | None,
        security_type: str,
        sort_field: str | None,
        ascending: bool,
        count: int,
    ) -> ScreenPage: ...

    def sector_industry(self, kind: str, key: str) -> SectorData: ...

    def calendar_events(self, kind: str, start: date, end: date, limit: int) -> pd.DataFrame: ...

    def ticker_events(self, symbol: str, earnings_limit: int) -> TickerEvents: ...

    def statement(self, symbol: str, statement: str, freq: str) -> pd.DataFrame: ...

    def valuation(self, symbol: str) -> pd.DataFrame: ...

    def key_stats(self, symbol: str) -> KeyStats: ...

    def analyst(self, symbol: str) -> AnalystData: ...

    def option_expirations(self, symbol: str) -> list[str]: ...

    def option_chain(self, symbol: str, expiry: str) -> OptionChain: ...

    def ticker_dataset(self, symbol: str, dataset: str) -> object: ...

    def open_live_stream(self) -> LiveStream: ...


class RateLimitedSession(curl_requests.Session):
    """A Chrome-impersonating ``curl_cffi`` session that paces every request it sends."""

    def __init__(self, limiter: RateLimiter) -> None:
        super().__init__(impersonate="chrome")
        self._limiter = limiter

    def request(self, method: Any, url: str, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        self._limiter.acquire()
        response = super().request(method, url, *args, **kwargs)
        if response.status_code == 429:
            self._limiter.report_rate_limited()
        elif response.status_code < 400:
            self._limiter.report_success()
        return response


class YFinanceGateway:
    """Production ``MarketDataGateway`` backed by yfinance."""

    def __init__(self, settings: Settings, *, limiter: RateLimiter | None = None) -> None:
        self._limiter = limiter or RateLimiter(
            settings.rate_limit_per_second, settings.rate_limit_burst
        )
        _configure_yfinance(settings)
        self._session = RateLimitedSession(self._limiter)

    def search_quotes(self, query: str, limit: int) -> list[SymbolMatch]:
        with self._yahoo_call():
            search = yf.Search(
                query,
                max_results=limit,
                news_count=0,
                lists_count=0,
                include_cb=False,
                recommended=0,
                session=self._session,
            )
        return [_symbol_match(quote) for quote in search.quotes][:limit]

    def lookup(self, query: str, kind: str, limit: int) -> list[SymbolMatch]:
        with self._yahoo_call():
            finder = yf.Lookup(query, session=self._session)
            frame = getattr(finder, f"get_{LOOKUP_KINDS[kind]}")(count=limit)
        rows = frame.head(limit).to_dict(orient="index")
        return [
            SymbolMatch(
                symbol=str(symbol),
                name=row.get("shortName"),
                type=str(row["quoteType"]).upper() if row.get("quoteType") else None,
                exchange=row.get("exchange"),
                sector=row.get("industryName"),  # Lookup's "industryName" holds the sector
            )
            for symbol, row in rows.items()
        ]

    def quote(self, symbol: str, *, details: bool = False) -> Quote:
        """Latest price from the 5-day chart (1 request); ``details`` adds quote summary fields."""
        quote = _quote_from_chart(self.history(symbol, period="5d", interval="1d"))
        if not details:
            return quote
        with self._yahoo_call():
            info = yf.Ticker(symbol, session=self._session).info
        return _with_details(quote, info)

    def market(self, region: str) -> tuple[MarketStatus | None, list[MarketIndex]]:
        with self._yahoo_call():
            market = yf.Market(region, session=self._session)
            status, summary = market.status, market.summary
        indices = [
            _market_index(entry) for entry in (summary or {}).values() if entry.get("symbol")
        ]
        return _market_status(status), indices

    def ticker_news(self, symbol: str, count: int, tab: str) -> list[NewsItem]:
        with self._yahoo_call():
            articles = yf.Ticker(symbol, session=self._session).get_news(count=count, tab=tab)
        return [
            _news_from_article(article["content"]) for article in articles if article.get("content")
        ]

    def search_news(self, query: str, count: int) -> list[NewsItem]:
        with self._yahoo_call():
            search = yf.Search(
                query,
                max_results=0,
                news_count=count,
                lists_count=0,
                include_cb=False,
                recommended=0,
                session=self._session,
            )
        return [_news_from_search(item) for item in search.news if item.get("uuid")]

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
        target = preset or _screen_query(query or {}, _QUERY_CLASSES[security_type])
        params: dict[str, Any] = {"count": count} if preset else {"size": count}
        if sort_field:
            params.update(sortField=sort_field, sortAsc=ascending)
        with self._yahoo_call():
            response = yf.screen(target, session=self._session, **params)
        quotes = response.get("quotes") or []
        rows = [_screen_row(quote) for quote in quotes if quote.get("symbol")]
        return ScreenPage(
            title=response.get("title"), total=response.get("total"), rows=rows[:count]
        )

    def sector_industry(self, kind: str, key: str) -> SectorData:
        with self._yahoo_call():
            if kind == "sector":
                sector = yf.Sector(key, session=self._session)
                return SectorData(
                    kind=kind,
                    key=key,
                    name=sector.name,
                    sector_key=None,
                    sector_name=None,
                    overview=sector.overview or {},
                    tables=_present(
                        top_companies=sector.top_companies, industries=sector.industries
                    ),
                    funds={
                        "top_etfs": sector.top_etfs or {},
                        "top_mutual_funds": sector.top_mutual_funds or {},
                    },
                )
            industry = yf.Industry(key, session=self._session)
            return SectorData(
                kind=kind,
                key=key,
                name=industry.name,
                sector_key=industry.sector_key,
                sector_name=industry.sector_name,
                overview=industry.overview or {},
                tables=_present(
                    top_companies=industry.top_companies,
                    top_performing_companies=industry.top_performing_companies,
                    top_growth_companies=industry.top_growth_companies,
                ),
                funds={},
            )

    def calendar_events(self, kind: str, start: date, end: date, limit: int) -> pd.DataFrame:
        with self._yahoo_call():
            # yfinance annotates this session as requests.Session but, like everywhere
            # else, accepts curl_cffi sessions.
            calendars = yf.Calendars(start=start, end=end, session=self._session)  # type: ignore[arg-type]
            fetch = {
                "earnings": calendars.get_earnings_calendar,
                "ipo": calendars.get_ipo_info_calendar,
                "economic": calendars.get_economic_events_calendar,
                "splits": calendars.get_splits_calendar,
            }[kind]
            frame = fetch(limit=limit)
        return frame if frame is not None else pd.DataFrame()

    def ticker_events(self, symbol: str, earnings_limit: int) -> TickerEvents:
        with self._yahoo_call():
            ticker = yf.Ticker(symbol, session=self._session)
            calendar = ticker.calendar or {}
            dates = ticker.get_earnings_dates(limit=earnings_limit)
        return TickerEvents(
            calendar=calendar, earnings_dates=dates if dates is not None else pd.DataFrame()
        )

    def statement(self, symbol: str, statement: str, freq: str) -> pd.DataFrame:
        """Line items (rows) by period (columns), newest period first."""
        with self._yahoo_call():
            ticker = yf.Ticker(symbol, session=self._session)
            fetch = {
                "income": ticker.get_income_stmt,
                "balance": ticker.get_balance_sheet,
                "cashflow": ticker.get_cash_flow,
            }[statement]
            frame = fetch(pretty=True, freq=freq)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            raise NotFound(f"Yahoo has no {freq} {statement} statement for {symbol}")
        return frame

    def valuation(self, symbol: str) -> pd.DataFrame:
        """Valuation measures (rows) by date (columns), the current value first."""
        with self._yahoo_call():
            frame = yf.Ticker(symbol, session=self._session).get_valuation_measures()
        if frame is None or frame.empty:
            raise NotFound(f"Yahoo has no valuation measures for {symbol}")
        return frame

    def key_stats(self, symbol: str) -> KeyStats:
        with self._yahoo_call():
            info = yf.Ticker(symbol, session=self._session).info
        return KeyStats(**{field: _float(info.get(key)) for field, key in _KEY_STATS.items()})

    def analyst(self, symbol: str) -> AnalystData:
        with self._yahoo_call():
            ticker = yf.Ticker(symbol, session=self._session)
            return AnalystData(
                price_targets=ticker.analyst_price_targets or {},
                recommendations=_frame(ticker.recommendations_summary),
                rating_changes=_frame(ticker.upgrades_downgrades),
                earnings_estimate=ticker.earnings_estimate,
                revenue_estimate=ticker.revenue_estimate,
                eps_trend=ticker.eps_trend,
                eps_revisions=ticker.eps_revisions,
                growth_estimates=ticker.growth_estimates,
            )

    def option_expirations(self, symbol: str) -> list[str]:
        with self._yahoo_call():
            return list(yf.Ticker(symbol, session=self._session).options)

    def option_chain(self, symbol: str, expiry: str) -> OptionChain:
        with self._yahoo_call():
            chain = yf.Ticker(symbol, session=self._session).option_chain(expiry)
        if chain.calls is None or chain.puts is None:
            raise NotFound(f"Yahoo has no option chain for {symbol} expiring {expiry}")
        return OptionChain(calls=chain.calls, puts=chain.puts, underlying=chain.underlying or {})

    def ticker_dataset(self, symbol: str, dataset: str) -> object:
        """The raw value of an allowlisted Ticker attribute (DataFrame, Series, dict, list...)."""
        path = TICKER_DATASETS[dataset]
        with self._yahoo_call():
            value: object = yf.Ticker(symbol, session=self._session)
            try:
                for attribute in path:
                    value = getattr(value, attribute)
            except (KeyError, yf_errors.YFDataException) as error:
                if path[0] != "funds_data":
                    raise
                raise NotFound(
                    f"{symbol} has no {dataset}; fund datasets exist only for ETFs and funds"
                ) from error
        if value is None:
            raise NotFound(f"Yahoo has no {dataset} for {symbol}")
        return value

    def open_live_stream(self) -> LiveStream:
        # verbose=False: yfinance would otherwise print to stdout, which carries MCP messages.
        return yf.AsyncWebSocket(verbose=False)

    def history(
        self,
        symbol: str,
        *,
        period: str | None = None,
        interval: str = "1d",
        start: date | None = None,
        end: date | None = None,
    ) -> PriceHistory:
        with self._yahoo_call():
            ticker = yf.Ticker(symbol, session=self._session)
            frame = ticker.history(
                period=period, interval=interval, start=start, end=end, actions=False
            )
            metadata = ticker.get_history_metadata()
        bars = _normalize_bars(frame)
        if bars.empty:
            raise NotFound(f"Yahoo returned no prices for {symbol} (interval {interval})")
        return PriceHistory(bars=bars, meta=_chart_meta(symbol, metadata, datetime.now(UTC)))

    @contextmanager
    def _yahoo_call(self) -> Iterator[None]:
        """Fail fast while paused, then translate whatever yfinance raises into DomainErrors."""
        remaining = self._limiter.cooldown_remaining()
        if remaining > 0:
            raise RateLimited(remaining)
        # yfinance caches some responses for the life of the process (Search, Market, quote
        # extras); drop them so a repeated call reaches Yahoo once our own TTL has expired.
        YfData.cache_get.cache_clear()
        try:
            yield
        except DomainError:
            raise
        except CooldownActive as error:
            raise RateLimited(error.retry_after) from error
        except yf_errors.YFRateLimitError as error:
            raise RateLimited(self._limiter.cooldown_remaining() or 30.0) from error
        except yf_errors.YFInvalidPeriodError as error:
            raise InvalidArgument(
                f"period {error.invalid_period!r} is not available for {error.ticker}",
                error.valid_ranges.split(", "),
            ) from error
        except yf_errors.YFTickerMissingError as error:
            raise NotFound(str(error)) from error
        except yf_errors.YFException as error:
            raise UpstreamError(f"Yahoo Finance error: {error}") from error
        except curl_requests.exceptions.HTTPError as error:
            raise _http_error(error) from error
        except curl_requests.exceptions.RequestException as error:
            raise UpstreamError(f"network error talking to Yahoo Finance: {error}") from error
        except Exception as error:
            logger.exception("unexpected failure inside yfinance")
            raise UpstreamError(
                f"unexpected {type(error).__name__} from yfinance: {error}"
            ) from error


def _http_error(error: Exception) -> DomainError:
    """404 means Yahoo has no such item; 400 means it rejected what was asked for."""
    status = getattr(getattr(error, "response", None), "status_code", None)
    if status == 404:
        return NotFound(f"Yahoo Finance has no such item (HTTP 404): {error}")
    if status == 400:
        return InvalidArgument(f"Yahoo Finance rejected the request (HTTP 400): {error}")
    return UpstreamError(f"Yahoo Finance answered HTTP {status}: {error}")


def _screen_query(node: Mapping[str, Any], query_class: type) -> Any:
    """Build a yfinance screener query from {"operator": ..., "operands": [...]} JSON."""
    if not isinstance(node, Mapping) or "operator" not in node or "operands" not in node:
        raise InvalidArgument('every query node needs "operator" and "operands"', SCREEN_OPERATORS)
    operands = [
        _screen_query(operand, query_class) if isinstance(operand, Mapping) else operand
        for operand in node["operands"]
    ]
    try:
        return query_class(str(node["operator"]).lower(), operands)
    except (ValueError, TypeError) as error:
        raise InvalidArgument(f"invalid screen query: {error}", SCREEN_OPERATORS) from error


def _screen_row(quote: Mapping[str, Any]) -> ScreenRow:
    return ScreenRow(
        symbol=quote["symbol"],
        name=quote.get("shortName") or quote.get("longName") or quote.get("displayName"),
        price=_float(quote.get("regularMarketPrice")),
        change_pct=_float(quote.get("regularMarketChangePercent")),
        volume=_float(quote.get("regularMarketVolume")),
        avg_volume_3m=_float(quote.get("averageDailyVolume3Month")),
        market_cap=_float(quote.get("marketCap")),
        exchange=quote.get("fullExchangeName") or quote.get("exchange"),
    )


def _frame(value: object) -> pd.DataFrame | None:
    """yfinance annotates some tables as DataFrame or dict; only DataFrames are used here."""
    return value if isinstance(value, pd.DataFrame) else None


def _present(**tables: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    return {name: table for name, table in tables.items() if table is not None}


def _configure_yfinance(settings: Settings) -> None:
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(settings.cache_dir))
    yf.config.debug.hide_exceptions = False  # raise, never log and return empty data
    yf.config.network.retries = 2  # transient network errors only; 429 is handled here
    yf.config.network.proxy = settings.proxy
    yf.config.locale.lang = settings.lang
    yf.config.locale.region = settings.region


def _symbol_match(quote: Mapping[str, Any]) -> SymbolMatch:
    return SymbolMatch(
        symbol=quote["symbol"],
        name=quote.get("longname") or quote.get("shortname"),
        type=quote.get("quoteType"),
        exchange=quote.get("exchDisp") or quote.get("exchange"),
        sector=quote.get("sectorDisp") or quote.get("sector"),
        industry=quote.get("industryDisp") or quote.get("industry"),
    )


def _normalize_bars(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=list(BAR_COLUMNS), index=pd.DatetimeIndex([], tz=UTC))
    bars = frame.rename(columns=str.lower).loc[:, list(BAR_COLUMNS)]
    index = pd.DatetimeIndex(bars.index)
    bars.index = index.tz_localize(UTC) if index.tz is None else index.tz_convert(UTC)
    return bars.dropna(subset=["close"]).sort_index()


def _chart_meta(symbol: str, metadata: Mapping[str, Any], now: datetime) -> ChartMeta:
    return ChartMeta(
        symbol=metadata.get("symbol") or symbol,
        name=metadata.get("longName") or metadata.get("shortName"),
        currency=metadata.get("currency"),
        exchange=metadata.get("fullExchangeName") or metadata.get("exchangeName"),
        instrument_type=metadata.get("instrumentType"),
        timezone=metadata.get("exchangeTimezoneName"),
        price=_float(metadata.get("regularMarketPrice")),
        change_pct=_float(metadata.get("regularMarketChangePercent")),
        day_high=_float(metadata.get("regularMarketDayHigh")),
        day_low=_float(metadata.get("regularMarketDayLow")),
        volume=_float(metadata.get("regularMarketVolume")),
        high_52w=_float(metadata.get("fiftyTwoWeekHigh")),
        low_52w=_float(metadata.get("fiftyTwoWeekLow")),
        market_time=_utc(metadata.get("regularMarketTime")),
        session=_session_state(metadata.get("currentTradingPeriod"), now),
    )


def _quote_from_chart(history: PriceHistory) -> Quote:
    meta, closes = history.meta, history.bars["close"]
    price = meta.price if meta.price is not None else float(closes.iloc[-1])
    previous_close = float(closes.iloc[-2]) if len(closes) > 1 else None
    change_pct = meta.change_pct
    if change_pct is None and previous_close:
        change_pct = (price / previous_close - 1) * 100
    return Quote(
        symbol=meta.symbol,
        name=meta.name,
        price=price,
        change_pct=None if change_pct is None else round(change_pct, 2),
        previous_close=previous_close,
        day_high=meta.day_high,
        day_low=meta.day_low,
        volume=meta.volume,
        high_52w=meta.high_52w,
        low_52w=meta.low_52w,
        currency=meta.currency,
        exchange=meta.exchange,
        market_state=meta.session,
        market_time=iso_utc(meta.market_time) if meta.market_time else None,
    )


def _with_details(quote: Quote, info: Mapping[str, Any]) -> Quote:
    details = QuoteDetails(
        market_cap=_float(info.get("marketCap")),
        average_volume=_float(info.get("averageVolume")),
        average_volume_10d=_float(info.get("averageVolume10days")),
        trailing_pe=_float(info.get("trailingPE")),
        forward_pe=_float(info.get("forwardPE")),
        dividend_yield_pct=_float(info.get("dividendYield")),
        beta=_float(info.get("beta")),
        fifty_day_average=_float(info.get("fiftyDayAverage")),
        two_hundred_day_average=_float(info.get("twoHundredDayAverage")),
        pre_market_price=_float(info.get("preMarketPrice")),
        post_market_price=_float(info.get("postMarketPrice")),
        bid=_float(info.get("bid")),
        ask=_float(info.get("ask")),
        sector=info.get("sector"),
        industry=info.get("industry"),
    )
    delay = info.get("exchangeDataDelayedBy")
    return quote.model_copy(
        update={
            "market_state": info.get("marketState") or quote.market_state,
            "quote_source": info.get("quoteSourceName"),
            "delay_min": int(delay) if isinstance(delay, int | float) else None,
            "details": details,
        }
    )


def _market_status(status: Mapping[str, Any] | None) -> MarketStatus | None:
    if not status:
        return None
    timezone = status.get("timezone")
    return MarketStatus(
        name=status.get("name"),
        state=status.get("status"),
        message=status.get("message"),
        opens_at=_iso(status.get("open")),
        closes_at=_iso(status.get("close")),
        timezone=timezone.get("$text") if isinstance(timezone, Mapping) else None,
    )


def _market_index(entry: Mapping[str, Any]) -> MarketIndex:
    delay = entry.get("exchangeDataDelayedBy")
    return MarketIndex(
        symbol=entry["symbol"],
        name=entry.get("shortName") or entry.get("longName"),
        type=entry.get("typeDisp") or entry.get("quoteType"),
        exchange=entry.get("fullExchangeName") or entry.get("exchange"),
        price=_float(entry.get("regularMarketPrice")),
        change=_float(entry.get("regularMarketChange")),
        change_pct=_float(entry.get("regularMarketChangePercent")),
        previous_close=_float(entry.get("regularMarketPreviousClose")),
        market_state=entry.get("marketState"),
        quote_source=entry.get("quoteSourceName"),
        delay_min=int(delay) if isinstance(delay, int | float) else None,
        market_time=_iso(entry.get("regularMarketTime")),
    )


def _news_from_article(content: Mapping[str, Any]) -> NewsItem:
    link = (content.get("clickThroughUrl") or {}).get("url") or (
        content.get("canonicalUrl") or {}
    ).get("url")
    tagged = (content.get("finance") or {}).get("stockTickers") or []
    return NewsItem(
        id=str(content["id"]),
        published_at=_iso(content.get("pubDate")),
        publisher=(content.get("provider") or {}).get("displayName"),
        url=link,
        tickers=[tag["symbol"] for tag in tagged if tag.get("symbol")],
        content_type=content.get("contentType"),
        untrusted=UntrustedText(
            title=content.get("title"),
            summary=content.get("summary") or content.get("description") or None,
        ),
    )


def _news_from_search(item: Mapping[str, Any]) -> NewsItem:
    return NewsItem(
        id=str(item["uuid"]),
        published_at=_iso(item.get("providerPublishTime")),
        publisher=item.get("publisher"),
        url=item.get("link"),
        tickers=list(item.get("relatedTickers") or []),
        content_type=item.get("type"),
        untrusted=UntrustedText(title=item.get("title")),
    )


def _iso(value: object) -> str | None:
    moment = _utc(value)
    return iso_utc(moment) if moment else None


def _session_state(periods: object, now: datetime) -> str | None:
    """Which trading session ``now`` falls in, from Yahoo's ``currentTradingPeriod``."""
    if not isinstance(periods, Mapping):
        return None
    for name in ("pre", "regular", "post"):
        window = periods.get(name) or {}
        start, end = _utc(window.get("start")), _utc(window.get("end"))
        if start is not None and end is not None and start <= now < end:
            return name.upper()
    return "CLOSED"


def _utc(value: object) -> datetime | None:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, UTC)
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    return None


def _float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None
