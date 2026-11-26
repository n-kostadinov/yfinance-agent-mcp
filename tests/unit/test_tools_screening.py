from __future__ import annotations

from typing import get_args

import pandas as pd
import pytest

from tests.fakes import FakeGateway
from yfinance_agent_mcp.errors import InvalidArgument, NotFound
from yfinance_agent_mcp.gateway import SCREENER_PRESETS, ScreenPage, SectorData
from yfinance_agent_mcp.models import ScreenRow
from yfinance_agent_mcp.tools.screening import (
    ScreenPreset,
    build_screen,
    build_sector_industry,
)


def rows(count: int, name: str = "Company") -> list[ScreenRow]:
    return [ScreenRow(symbol=f"S{n}", name=f"{name} {n}", price=10.0 + n) for n in range(count)]


def test_tool_offers_exactly_the_screens_yfinance_predefines() -> None:
    assert set(get_args(ScreenPreset)) == set(SCREENER_PRESETS)


def test_predefined_screen_returns_compact_rows() -> None:
    gateway = FakeGateway()
    gateway.screens["day_gainers"] = ScreenPage(title="Day Gainers", total=120, rows=rows(3))

    result = build_screen(gateway, "day_gainers", None, "equity", None, False, 25)

    assert (result.screen, result.title, result.total) == ("day_gainers", "Day Gainers", 120)
    assert [row.symbol for row in result.rows] == ["S0", "S1", "S2"]


def test_large_screen_is_capped_and_fits_the_default_budget() -> None:
    gateway = FakeGateway()
    gateway.screens["day_gainers"] = ScreenPage(
        title="Day Gainers", total=250, rows=rows(250, name="A long company name " * 3)
    )

    result = build_screen(gateway, "day_gainers", None, "equity", None, False, 25)

    assert len(result.rows) == 25
    assert len(result.model_dump_json()) <= 20_000


@pytest.mark.parametrize(
    ("preset", "query"),
    [("day_gainers", {"operator": "gt", "operands": ["percentchange", 3]}), (None, None)],
)
def test_screen_needs_exactly_one_of_preset_or_query(
    preset: ScreenPreset | None, query: dict[str, object] | None
) -> None:
    with pytest.raises(InvalidArgument, match="either a preset or a query"):
        build_screen(FakeGateway(), preset, query, "equity", None, False, 25)


def sector(top_companies_count: int = 3) -> SectorData:
    companies = pd.DataFrame(
        {
            "name": [f"Company {n}" for n in range(top_companies_count)],
            "rating": ["Buy"] * top_companies_count,
            "market weight": [0.1] * top_companies_count,
        },
        index=pd.Index([f"C{n}" for n in range(top_companies_count)], name="symbol"),
    )
    industries = pd.DataFrame(
        {"name": ["Semiconductors"], "symbol": ["^YH31130020"], "market weight": [0.3]},
        index=pd.Index(["semiconductors"], name="key"),
    )
    return SectorData(
        kind="sector",
        key="technology",
        name="Technology",
        sector_key=None,
        sector_name=None,
        overview={"companies_count": 800, "description": "D" * 2_000},
        tables={"top_companies": companies, "industries": industries},
        funds={"top_etfs": {"QQQ": "Invesco QQQ Trust"}, "top_mutual_funds": {}},
    )


def test_sector_tables_become_records_with_readable_keys() -> None:
    gateway = FakeGateway()
    gateway.sectors[("sector", "technology")] = sector()

    result = build_sector_industry(gateway, "sector", "technology")

    assert result.top_companies[0] == {
        "symbol": "C0",
        "name": "Company 0",
        "rating": "Buy",
        "market_weight": 0.1,
    }
    assert result.industries == [
        {
            "key": "semiconductors",
            "name": "Semiconductors",
            "symbol": "^YH31130020",
            "market_weight": 0.3,
        }
    ]
    assert result.top_etfs == [{"symbol": "QQQ", "name": "Invesco QQQ Trust"}]
    assert len(str(result.overview["description"])) == 500


def test_sector_tables_are_capped_at_25_rows() -> None:
    gateway = FakeGateway()
    gateway.sectors[("sector", "technology")] = sector(top_companies_count=60)

    result = build_sector_industry(gateway, "sector", "technology")

    assert len(result.top_companies) == 25


def test_unknown_sector_lists_the_valid_sector_keys() -> None:
    with pytest.raises(NotFound, match="technology, utilities"):
        build_sector_industry(FakeGateway(), "sector", "tech")
