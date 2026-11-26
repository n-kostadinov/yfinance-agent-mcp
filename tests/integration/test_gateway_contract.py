"""The real YFinanceGateway against a fake Yahoo at the HTTP boundary (no network).

What stays unverified here: Yahoo's real payloads and throttling; the live tests cover those.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pandas as pd
import pytest
from curl_cffi import requests as curl_requests
from yfinance.data import YfData

from tests.fakes import FakeGateway
from tests.unit.fake_clock import FakeClock
from yfinance_agent_mcp.config import Settings
from yfinance_agent_mcp.errors import InvalidArgument, NotFound, RateLimited
from yfinance_agent_mcp.gateway import MarketDataGateway, YFinanceGateway
from yfinance_agent_mcp.models import SymbolMatch
from yfinance_agent_mcp.ratelimit import RateLimiter

SEARCH_PATH = "/v1/finance/search"


@dataclass
class FakeResponse:
    status_code: int
    text: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def content(self) -> bytes:
        return self.text.encode()

    def json(self) -> Any:
        return json.loads(self.text)


def chart_body(symbol: str, *, closes: list[float]) -> dict[str, Any]:
    now = int(time.time())
    period = {"timezone": "EST", "gmtoffset": -18_000}
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "currency": "USD",
                        "symbol": symbol,
                        "exchangeName": "NMS",
                        "fullExchangeName": "NasdaqGS",
                        "instrumentType": "EQUITY",
                        "regularMarketTime": now - 60,
                        "gmtoffset": -18_000,
                        "timezone": "EST",
                        "exchangeTimezoneName": "America/New_York",
                        "regularMarketPrice": closes[-1],
                        "fiftyTwoWeekHigh": 300.0,
                        "fiftyTwoWeekLow": 150.0,
                        "longName": "Apple Inc.",
                        "priceHint": 2,
                        "currentTradingPeriod": {
                            "pre": {**period, "start": now - 7_200, "end": now - 3_600},
                            "regular": {**period, "start": now - 3_600, "end": now + 3_600},
                            "post": {**period, "start": now + 3_600, "end": now + 7_200},
                        },
                        "dataGranularity": "1d",
                        "range": "5d",
                        "validRanges": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "max"],
                    },
                    "timestamp": [1_763_649_000 + day * 86_400 for day in range(len(closes))],
                    "indicators": {
                        "quote": [
                            {
                                "open": closes,
                                "high": [c + 1 for c in closes],
                                "low": [c - 1 for c in closes],
                                "close": closes,
                                "volume": [1_000_000] * len(closes),
                            }
                        ],
                        "adjclose": [{"adjclose": closes}],
                    },
                }
            ],
            "error": None,
        }
    }


class FakeYahoo:
    """Answers the Yahoo endpoints yfinance calls and records every request path."""

    def __init__(self) -> None:
        self.paths: list[str] = []
        self.search_status = 200
        self.chart: dict[str, Any] = chart_body("AAPL", closes=[270.0, 271.5])

    def handle(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        parts = urlsplit(url)
        self.paths.append(parts.path)
        params = kwargs.get("params") or {}
        if parts.path == "/v1/test/getcrumb":
            return FakeResponse(200, "fake-crumb", url)
        if parts.path == SEARCH_PATH:
            if self.search_status == 429:
                return FakeResponse(429, "Too Many Requests", url)
            quotes = [
                {
                    "symbol": "NVDA",
                    "longname": "NVIDIA Corporation",
                    "quoteType": "EQUITY",
                    "exchDisp": "NASDAQ",
                }
            ]
            return FakeResponse(200, json.dumps({"quotes": quotes, "news": []}), url)
        if parts.path.startswith("/v8/finance/chart/"):
            if params.get("range") == "1d":  # yfinance's timezone lookup
                return FakeResponse(200, json.dumps(chart_body("AAPL", closes=[1.0])), url)
            return FakeResponse(200, json.dumps(self.chart), url)
        return FakeResponse(200, "", url)  # cookie and consent pages


@pytest.fixture
def yahoo(monkeypatch: pytest.MonkeyPatch) -> FakeYahoo:
    fake = FakeYahoo()

    def fake_request(_session: object, method: str, url: str, *_args: Any, **kwargs: Any):
        return fake.handle(method, url, **kwargs)

    monkeypatch.setattr(curl_requests.Session, "request", fake_request)
    return fake


@pytest.fixture
def gateway(tmp_path: Path, yahoo: FakeYahoo) -> YFinanceGateway:
    return YFinanceGateway(Settings(cache_dir=tmp_path))


def test_repeated_searches_reach_yahoo_every_time(
    gateway: YFinanceGateway, yahoo: FakeYahoo
) -> None:
    first = gateway.search_quotes("NVDA", 5)
    second = gateway.search_quotes("NVDA", 5)

    assert yahoo.paths.count(SEARCH_PATH) == 2
    expected = SymbolMatch(
        symbol="NVDA", name="NVIDIA Corporation", type="EQUITY", exchange="NASDAQ"
    )
    assert first == second == [expected]


def test_rate_limit_maps_to_rate_limited_and_pauses_later_requests(
    gateway: YFinanceGateway, yahoo: FakeYahoo
) -> None:
    yahoo.search_status = 429

    with pytest.raises(RateLimited) as limited:
        gateway.search_quotes("NVDA", 5)
    requests_before = len(yahoo.paths)
    with pytest.raises(RateLimited):
        gateway.search_quotes("NVDA", 5)

    assert limited.value.retry_after == 30
    assert len(yahoo.paths) == requests_before


def test_missing_prices_raise_not_found_instead_of_an_empty_result(
    gateway: YFinanceGateway, yahoo: FakeYahoo
) -> None:
    yahoo.chart = {
        "chart": {
            "result": None,
            "error": {"code": "Not Found", "description": "No data found, symbol may be delisted"},
        }
    }

    with pytest.raises(NotFound, match="No data found, symbol may be delisted"):
        gateway.history("GONE", period="5d")


def test_history_is_normalized_to_utc_bars_with_quote_fields(gateway: YFinanceGateway) -> None:
    history = gateway.history("AAPL", period="5d")

    assert list(history.bars.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(history.bars.index, pd.DatetimeIndex)
    assert str(history.bars.index.tz) == "UTC"
    assert history.bars["close"].tolist() == [270.0, 271.5]
    assert (history.meta.price, history.meta.currency, history.meta.session) == (
        271.5,
        "USD",
        "REGULAR",
    )


def test_every_request_waits_for_the_rate_limiter(tmp_path: Path, yahoo: FakeYahoo) -> None:
    clock = FakeClock()
    limiter = RateLimiter(1.0, 1, clock=clock, sleep=clock.sleep)
    gateway = YFinanceGateway(Settings(cache_dir=tmp_path), limiter=limiter)

    gateway.search_quotes("NVDA", 5)
    gateway.search_quotes("NVDA", 5)

    assert clock.sleeps == [1.0] * (len(yahoo.paths) - 1)


def test_gateway_calls_write_nothing_to_stdout(
    gateway: YFinanceGateway, capfd: pytest.CaptureFixture[str]
) -> None:
    gateway.search_quotes("NVDA", 5)
    gateway.history("AAPL", period="5d")

    assert capfd.readouterr().out == ""


def test_installed_yfinance_still_offers_the_cache_clear_hook() -> None:
    assert callable(YfData.cache_get.cache_clear)


def test_fake_gateway_satisfies_the_gateway_port() -> None:
    port: MarketDataGateway = FakeGateway()

    assert port.search_quotes("anything", 1) == []


def test_invalid_screen_query_is_rejected_with_the_valid_operators(
    gateway: YFinanceGateway, yahoo: FakeYahoo
) -> None:
    query = {"operator": "near", "operands": ["percentchange", 3]}

    with pytest.raises(InvalidArgument, match="Valid values: and, or, eq, gt"):
        gateway.screen(
            preset=None,
            query=query,
            security_type="equity",
            sort_field=None,
            ascending=False,
            count=5,
        )
    assert yahoo.paths == []
