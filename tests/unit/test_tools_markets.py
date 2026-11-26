from __future__ import annotations

import pytest

from tests.fakes import FakeGateway
from yfinance_agent_mcp.errors import NotFound
from yfinance_agent_mcp.models import MarketIndex, MarketStatus, Quote, SymbolMatch
from yfinance_agent_mcp.tools.markets import (
    build_market_overview,
    build_quotes,
    build_symbol_search,
)

NVDA = SymbolMatch(symbol="NVDA", name="NVIDIA Corporation", type="EQUITY", exchange="NASDAQ")
NVDA_DE = SymbolMatch(symbol="NVD.DE", name="NVIDIA CORP.", type="EQUITY", exchange="GER")


def quote(symbol: str, *, delay_min: int | None = None) -> Quote:
    return Quote(symbol=symbol, price=100.0, currency="USD", delay_min=delay_min)


def test_any_kind_uses_full_text_search_and_a_specific_kind_uses_lookup() -> None:
    gateway = FakeGateway()
    gateway.symbol_matches["nvidia"] = [NVDA]
    gateway.lookups[("nvidia", "equity")] = [NVDA, NVDA_DE]

    anything = build_symbol_search(gateway, "nvidia", "any", 10)
    equities = build_symbol_search(gateway, "nvidia", "equity", 10)

    assert anything.matches == [NVDA]
    assert equities.matches == [NVDA, NVDA_DE]


def test_search_without_matches_warns_instead_of_failing() -> None:
    result = build_symbol_search(FakeGateway(), "zzzz", "any", 10)

    assert result.matches == []
    assert any("No matches for 'zzzz'" in warning for warning in result.warnings)


def test_quotes_list_failed_symbols_next_to_the_quotes_that_worked() -> None:
    gateway = FakeGateway()
    gateway.quotes = {"AAPL": quote("AAPL"), "MSFT": quote("MSFT")}

    result = build_quotes(gateway, ["AAPL", "GONE", "MSFT"], include_details=False)

    assert [q.symbol for q in result.quotes] == ["AAPL", "MSFT"]
    assert [(e.symbol, e.error) for e in result.errors] == [("GONE", "not_found")]


def test_quotes_without_details_explain_how_to_get_delay_information() -> None:
    gateway = FakeGateway()
    gateway.quotes["AAPL"] = quote("AAPL", delay_min=15)

    result = build_quotes(gateway, ["AAPL"], include_details=False)

    assert result.quotes[0].delay_min is None
    assert any("include_details=true" in warning for warning in result.warnings)


def test_quotes_with_details_warn_about_delayed_symbols() -> None:
    gateway = FakeGateway()
    gateway.quotes = {
        "SAP.DE": quote("SAP.DE", delay_min=15),
        "BTC-USD": quote("BTC-USD", delay_min=0),
    }

    result = build_quotes(gateway, ["SAP.DE", "BTC-USD"], include_details=True)

    assert result.warnings == ["Delayed by up to 15 min: SAP.DE."]


def test_quotes_fail_when_no_symbol_has_data() -> None:
    with pytest.raises(NotFound):
        build_quotes(FakeGateway(), ["GONE"], include_details=False)


def test_market_overview_reports_status_indices_and_delays() -> None:
    gateway = FakeGateway()
    status = MarketStatus(name="U.S. markets", state="open")
    indices = [
        MarketIndex(symbol="^GSPC", price=6_000.0, delay_min=0),
        MarketIndex(symbol="ES=F", price=6_010.0, delay_min=10),
    ]
    gateway.markets["US"] = (status, indices)

    result = build_market_overview(gateway, "US")

    assert (result.region, result.status, result.indices) == ("US", status, indices)
    assert result.warnings == ["1 of 2 prices are delayed by up to 10 min."]
