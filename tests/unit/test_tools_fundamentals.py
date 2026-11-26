from __future__ import annotations

import pandas as pd
import pytest

from tests.fakes import FakeGateway
from yfinance_agent_mcp.errors import InvalidArgument
from yfinance_agent_mcp.gateway import AnalystData
from yfinance_agent_mcp.models import KeyStats
from yfinance_agent_mcp.tools.fundamentals import build_analyst_view, build_fundamentals

PERIODS = [pd.Timestamp("2026-09-30"), pd.Timestamp("2026-06-30")]


def income_statement() -> pd.DataFrame:
    return pd.DataFrame(
        {PERIODS[0]: [102.5e9, 27.5e9, 1.85, 0.21], PERIODS[1]: [94.0e9, 23.4e9, 1.57, 0.2]},
        index=["Total Revenue", "Net Income", "Diluted EPS", "Tax Rate For Calcs"],
    )


def gateway_with_income() -> FakeGateway:
    gateway = FakeGateway()
    gateway.statements[("AAPL", "income", "quarterly")] = income_statement()
    return gateway


def test_concise_statement_has_key_line_items_per_period_newest_first() -> None:
    result = build_fundamentals(gateway_with_income(), "AAPL", "income", "quarterly", "concise")

    assert result.periods == [
        {
            "period": "2026-09-30",
            "total_revenue": 102.5e9,
            "net_income": 27.5e9,
            "diluted_eps": 1.85,
        },
        {
            "period": "2026-06-30",
            "total_revenue": 94.0e9,
            "net_income": 23.4e9,
            "diluted_eps": 1.57,
        },
    ]


def test_detailed_statement_includes_every_line_item() -> None:
    result = build_fundamentals(gateway_with_income(), "AAPL", "income", "quarterly", "detailed")

    assert result.periods[0]["tax_rate_for_calcs"] == 0.21


def test_trailing_balance_sheet_is_rejected() -> None:
    with pytest.raises(InvalidArgument, match=r"trailing.*income and cashflow"):
        build_fundamentals(FakeGateway(), "AAPL", "balance", "trailing", "concise")


def test_valuation_measures_become_one_record_per_date() -> None:
    gateway = FakeGateway()
    gateway.valuations["AAPL"] = pd.DataFrame(
        {"Current": [4.1e12, 35.2], "9/30/2026": [3.9e12, 33.0]},
        index=["Market Cap", "Trailing P/E"],
    )

    result = build_fundamentals(gateway, "AAPL", "valuation", "quarterly", "concise")

    assert result.freq is None
    assert result.periods == [
        {"period": "Current", "market_cap": 4.1e12, "trailing_p_e": 35.2},
        {"period": "9/30/2026", "market_cap": 3.9e12, "trailing_p_e": 33.0},
    ]


def test_key_stats_come_from_the_gateway() -> None:
    gateway = FakeGateway()
    gateway.stats["AAPL"] = KeyStats(trailing_pe=35.2, profit_margin=0.27)

    result = build_fundamentals(gateway, "AAPL", "key_stats", "yearly", "concise")

    assert result.key_stats == KeyStats(trailing_pe=35.2, profit_margin=0.27)
    assert result.periods == []


def analyst_data(rating_rows: int) -> AnalystData:
    ratings = pd.DataFrame(
        {
            "Firm": [f"Bank {n}" for n in range(rating_rows)],
            "ToGrade": ["Buy"] * rating_rows,
            "FromGrade": ["Hold"] * rating_rows,
            "Action": ["up"] * rating_rows,
            "currentPriceTarget": [300.0] * rating_rows,
        },
        index=pd.Index(
            pd.date_range("2026-11-20", periods=rating_rows, freq="-1D", tz="UTC"),
            name="GradeDate",
        ),
    )
    estimates = pd.DataFrame(
        {"avg": [2.9, 1.9], "numberOfAnalysts": [30, 28]}, index=pd.Index(["0q", "+1q"])
    )
    recommendations = pd.DataFrame(
        {
            "period": ["0m"],
            "strongBuy": [7],
            "buy": [20],
            "hold": [12],
            "sell": [1],
            "strongSell": [1],
        }
    )
    return AnalystData(
        price_targets={"current": 271.5, "mean": 300.2, "high": 350.0, "low": 200.0},
        recommendations=recommendations,
        rating_changes=ratings,
        earnings_estimate=estimates,
        revenue_estimate=None,
        eps_trend=None,
        eps_revisions=None,
        growth_estimates=None,
    )


def test_analyst_view_keeps_the_latest_rating_changes_within_the_default_budget() -> None:
    gateway = FakeGateway()
    gateway.analysts["AAPL"] = analyst_data(rating_rows=1_000)

    result = build_analyst_view(gateway, "AAPL", 10)

    assert len(result.rating_changes) == 10
    assert result.rating_changes[0]["grade_date"] == "2026-11-20T00:00:00Z"
    assert len(result.model_dump_json()) <= 20_000


def test_analyst_tables_become_records_keyed_by_period() -> None:
    gateway = FakeGateway()
    gateway.analysts["AAPL"] = analyst_data(rating_rows=1)

    result = build_analyst_view(gateway, "AAPL", 10)

    assert result.price_targets["mean"] == 300.2
    assert result.earnings_estimate == [
        {"period": "0q", "avg": 2.9, "number_of_analysts": 30},
        {"period": "+1q", "avg": 1.9, "number_of_analysts": 28},
    ]
    assert result.recommendations[0]["strong_buy"] == 7
    assert result.revenue_estimate == []
