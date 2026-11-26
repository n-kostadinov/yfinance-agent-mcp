"""Promises every tool keeps: read-only annotations, size budgets, as_of, actionable errors."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import pytest
from mcp import Client
from mcp.types import TextContent

from tests.fakes import FakeGateway, make_history
from yfinance_agent_mcp.errors import (
    DomainError,
    InvalidArgument,
    NotFound,
    RateLimited,
    UpstreamError,
)
from yfinance_agent_mcp.gateway import AnalystData, OptionChain, ScreenPage, SectorData
from yfinance_agent_mcp.models import (
    MarketIndex,
    MarketStatus,
    NewsItem,
    Quote,
    QuoteDetails,
    ScreenRow,
    SymbolMatch,
    UntrustedText,
)

pytestmark = pytest.mark.anyio

SYMBOLS_25 = [f"S{n}" for n in range(25)]
SYMBOLS_10 = SYMBOLS_25[:10]
LONG = "x" * 500
BUDGETS = {"concise": 20_000, "detailed": 80_000}

# One call per tool, with the largest arguments it accepts.
TOOL_CALLS: dict[str, dict[str, Any]] = {
    "search_symbols": {"query": "big"},
    "get_quotes": {"symbols": SYMBOLS_25, "include_details": True},
    "get_market_overview": {"region": "US"},
    "get_price_history": {
        "symbols": SYMBOLS_10,
        "period": "5d",
        "interval": "1m",
        "mode": "bars",
        "bars": 500,
    },
    "get_news": {"symbols": SYMBOLS_10, "count": 20},
    "screen_securities": {"preset": "day_gainers"},
    "get_sector_industry": {"kind": "sector", "key": "technology"},
    "get_events": {"kind": "earnings", "limit": 50},
    "get_fundamentals": {"symbol": "S0", "statement": "income", "freq": "quarterly"},
    "get_analyst_view": {"symbol": "S0", "rating_changes": 50},
    "get_options": {"symbol": "S0", "strikes_each_side": 25},
    "get_ticker_dataset": {"symbol": "S0", "dataset": "info"},
    "get_live_quotes": {"symbols": SYMBOLS_25, "wait_seconds": 0.2},
}


def table(rows: int, columns: int, *, index_name: str | None = None) -> pd.DataFrame:
    data = {f"Column {c}": [f"{LONG[:40]}{r}" for r in range(rows)] for c in range(columns)}
    frame = pd.DataFrame(data)
    if index_name:
        frame.index = pd.Index([f"K{r}" for r in range(rows)], name=index_name)
    return frame


def fill_with_oversized_data(gateway: FakeGateway) -> None:
    gateway.symbol_matches["big"] = [SymbolMatch(symbol=f"S{n}", name=LONG) for n in range(10)]
    details = QuoteDetails(sector=LONG, industry=LONG)
    for symbol in SYMBOLS_25:
        gateway.quotes[symbol] = Quote(symbol=symbol, name=LONG, price=1.0, details=details)
        gateway.histories[symbol] = make_history(
            symbol, [100.0 + i / 100 for i in range(3_000)], freq="min"
        )
        gateway.ticker_articles[symbol] = [
            NewsItem(
                id=f"{symbol}-{n}",
                published_at=f"2026-11-{10 + n % 15:02d}T10:00:00Z",
                tickers=SYMBOLS_25,
                untrusted=UntrustedText(title=LONG * 2, summary=LONG * 10),
            )
            for n in range(20)
        ]
        gateway.live_ticks[symbol] = {"id": symbol, "price": 1.0, "market_hours": LONG[:20]}
    gateway.markets["US"] = (
        MarketStatus(name=LONG, message=LONG),
        [MarketIndex(symbol=f"I{n}", name=LONG) for n in range(300)],
    )
    gateway.screens["day_gainers"] = ScreenPage(
        title=LONG, total=250, rows=[ScreenRow(symbol=f"S{n}", name=LONG) for n in range(250)]
    )
    gateway.sectors[("sector", "technology")] = SectorData(
        kind="sector",
        key="technology",
        name="Technology",
        sector_key=None,
        sector_name=None,
        overview={"description": LONG * 20},
        tables={
            "top_companies": table(200, 4, index_name="symbol"),
            "industries": table(200, 4, index_name="key"),
        },
        funds={"top_etfs": {f"E{n}": LONG for n in range(200)}, "top_mutual_funds": {}},
    )
    gateway.calendars["earnings"] = table(500, 6, index_name="Symbol")
    statement = table(300, 20)
    statement.index = pd.Index(["Total Revenue", "Net Income"] + [f"Item {n}" for n in range(298)])
    statement.columns = pd.date_range("2021-03-31", periods=20, freq="QE")
    gateway.statements[("S0", "income", "quarterly")] = statement
    gateway.analysts["S0"] = AnalystData(
        price_targets={"mean": 1.0},
        recommendations=table(100, 6),
        rating_changes=table(2_000, 5, index_name="GradeDate"),
        earnings_estimate=table(100, 8, index_name="period"),
        revenue_estimate=table(100, 8, index_name="period"),
        eps_trend=table(100, 8, index_name="period"),
        eps_revisions=table(100, 8, index_name="period"),
        growth_estimates=table(100, 8, index_name="period"),
    )
    strikes = pd.DataFrame(
        {"contractSymbol": [LONG[:30]] * 1_000, "strike": [float(s) for s in range(1_000)]}
    )
    gateway.expirations["S0"] = ["2026-11-28"]
    gateway.chains[("S0", "2026-11-28")] = OptionChain(
        calls=strikes, puts=strikes, underlying={"regularMarketPrice": 500.0}
    )
    gateway.datasets[("S0", "info")] = {f"field_{n}": LONG for n in range(2_000)}


async def test_the_server_offers_exactly_the_thirteen_read_only_tools(client: Client) -> None:
    tools = (await client.list_tools()).tools

    assert {tool.name for tool in tools} == set(TOOL_CALLS)
    for tool in tools:
        assert tool.annotations is not None, tool.name
        assert (tool.annotations.read_only_hint, tool.annotations.open_world_hint) == (True, True)
        assert tool.title, tool.name
        assert tool.description, tool.name


@pytest.mark.parametrize("response_format", ["concise", "detailed"])
@pytest.mark.parametrize("tool", sorted(TOOL_CALLS))
async def test_every_tool_stays_within_its_budget_and_reports_as_of(
    client: Client, fake_gateway: FakeGateway, tool: str, response_format: str
) -> None:
    fill_with_oversized_data(fake_gateway)

    result = await client.call_tool(tool, {**TOOL_CALLS[tool], "response_format": response_format})

    assert result.is_error is False, result.content
    assert result.structured_content is not None
    size = len(json.dumps(result.structured_content, separators=(",", ":")))
    assert size <= BUDGETS[response_format], (tool, size)
    assert result.structured_content["as_of"].endswith("Z")


def error_text(result: Any) -> str:
    assert result.is_error is True
    text = result.content[0]
    assert isinstance(text, TextContent)
    return text.text


@pytest.mark.parametrize("tool", sorted(TOOL_CALLS))
async def test_every_tool_turns_a_rate_limit_into_retry_advice(
    client: Client, fake_gateway: FakeGateway, tool: str
) -> None:
    fake_gateway.fail_everything(RateLimited(42))

    result = await client.call_tool(tool, TOOL_CALLS[tool])

    assert "rate_limited: Yahoo Finance is rate-limiting this server. Retry in 42 s" in error_text(
        result
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (NotFound("$GONE: possibly delisted"), "not_found: $GONE: possibly delisted"),
        (InvalidArgument("bad period", ["1d", "5d"]), "invalid_argument: bad period. Valid values"),
        (UpstreamError("Yahoo answered HTTP 503"), "upstream_error: Yahoo answered HTTP 503"),
    ],
)
async def test_each_error_kind_reaches_the_agent_with_its_code_and_advice(
    client: Client, fake_gateway: FakeGateway, error: DomainError, expected: str
) -> None:
    fake_gateway.fail_everything(error)

    result = await client.call_tool("get_quotes", {"symbols": ["GONE"]})

    assert expected in error_text(result)
