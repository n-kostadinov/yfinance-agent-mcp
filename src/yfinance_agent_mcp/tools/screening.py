"""Find candidates with Yahoo's screeners, and see who leads a sector or industry."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Literal

import pandas as pd
from mcp.server import MCPServer
from pydantic import Field, JsonValue

from yfinance_agent_mcp.errors import InvalidArgument, NotFound
from yfinance_agent_mcp.gateway import SCREEN_OPERATORS, MarketDataGateway
from yfinance_agent_mcp.models import ScreenResult, SectorIndustryResult
from yfinance_agent_mcp.shaping import (
    frame_to_records,
    snake_case,
    to_json_value,
    truncate_text,
)
from yfinance_agent_mcp.tools.context import READ_ONLY, ResponseFormatParam, ToolContext, utc_now

ScreenPreset = Literal[
    "aggressive_small_caps",
    "day_gainers",
    "day_losers",
    "growth_technology_stocks",
    "most_actives",
    "most_shorted_stocks",
    "small_cap_gainers",
    "undervalued_growth_stocks",
    "undervalued_large_caps",
    "conservative_foreign_funds",
    "high_yield_bond",
    "portfolio_anchors",
    "solid_large_growth_funds",
    "solid_midcap_growth_funds",
    "top_mutual_funds",
    "top_etfs_us",
    "top_performing_etfs",
    "technology_etfs",
    "bond_etfs",
]
SecurityType = Literal["equity", "fund", "etf"]
SectorKind = Literal["sector", "industry"]
SECTOR_KEYS = (
    "basic-materials",
    "communication-services",
    "consumer-cyclical",
    "consumer-defensive",
    "energy",
    "financial-services",
    "healthcare",
    "industrials",
    "real-estate",
    "technology",
    "utilities",
)
_MAX_ROWS = 25
_QUERY_DESCRIPTION = (
    "A custom screen instead of a preset: "
    '{"operator": "and", "operands": [{"operator": "gt", "operands": ["percentchange", 3]}, '
    '{"operator": "eq", "operands": ["region", "us"]}]}. '
    f"Operators: {', '.join(SCREEN_OPERATORS)}."
)
_KEY_DESCRIPTION = (
    f"Sector key ({', '.join(SECTOR_KEYS)}) or an industry key such as 'semiconductors' "
    "(listed in a sector's `industries`)."
)
_DESCRIPTION_CHARS = 500


def build_screen(
    gateway: MarketDataGateway,
    preset: ScreenPreset | None,
    query: Mapping[str, Any] | None,
    security_type: SecurityType,
    sort_field: str | None,
    ascending: bool,
    count: int,
) -> ScreenResult:
    if (preset is None) == (query is None):
        raise InvalidArgument("give either a preset or a query, not both or neither")
    page = gateway.screen(
        preset=preset,
        query=query,
        security_type=security_type,
        sort_field=sort_field,
        ascending=ascending,
        count=count,
    )
    warnings = [] if page.rows else ["No securities match; loosen the query or try another preset."]
    return ScreenResult(
        as_of=utc_now(),
        screen=preset or "custom",
        title=page.title,
        total=page.total,
        rows=page.rows[:count],
        warnings=warnings,
    )


def build_sector_industry(
    gateway: MarketDataGateway, kind: SectorKind, key: str
) -> SectorIndustryResult:
    try:
        data = gateway.sector_industry(kind, key)
    except NotFound as error:
        hint = (
            f"valid sector keys: {', '.join(SECTOR_KEYS)}"
            if kind == "sector"
            else "get a sector's `industries` to find industry keys"
        )
        raise NotFound(f"no {kind} {key!r} on Yahoo Finance; {hint}") from error
    overview = {str(k): to_json_value(v) for k, v in data.overview.items()}
    if isinstance(overview.get("description"), str):
        overview["description"] = truncate_text(str(overview["description"]), _DESCRIPTION_CHARS)

    def table(name: str) -> list[dict[str, JsonValue]]:
        return _table_records(data.tables[name]) if name in data.tables else []

    return SectorIndustryResult(
        as_of=utc_now(),
        kind=kind,
        key=key,
        name=data.name,
        sector_key=data.sector_key,
        sector_name=data.sector_name,
        overview=overview,
        top_companies=table("top_companies"),
        industries=table("industries"),
        top_performing_companies=table("top_performing_companies"),
        top_growth_companies=table("top_growth_companies"),
        top_etfs=_fund_records(data.funds.get("top_etfs", {})),
        top_mutual_funds=_fund_records(data.funds.get("top_mutual_funds", {})),
    )


def _table_records(table: pd.DataFrame) -> list[dict[str, JsonValue]]:
    readable = table.rename(columns=snake_case)
    page = frame_to_records(readable, index_name=str(table.index.name or "key"), limit=_MAX_ROWS)
    return page.records  # type: ignore[return-value]


def _fund_records(listing: Mapping[str, str]) -> list[dict[str, JsonValue]]:
    return [{"symbol": symbol, "name": name} for symbol, name in list(listing.items())[:_MAX_ROWS]]


def register(server: MCPServer, context: ToolContext) -> None:
    @server.tool(title="Screen securities", annotations=READ_ONLY)
    def screen_securities(
        preset: Annotated[
            ScreenPreset | None,
            Field(description="A predefined Yahoo screen, e.g. 'day_gainers' or 'most_actives'."),
        ] = None,
        query: Annotated[
            dict[str, Any] | None,
            Field(description=_QUERY_DESCRIPTION),
        ] = None,
        security_type: Annotated[
            SecurityType, Field(description="What a custom query screens.")
        ] = "equity",
        sort_field: Annotated[
            str | None, Field(description="Yahoo field to sort by, e.g. 'percentchange'.")
        ] = None,
        ascending: bool = False,
        count: Annotated[int, Field(ge=1, le=25, description="Rows to return.")] = 25,
        response_format: ResponseFormatParam = "concise",
    ) -> ScreenResult:
        """Find candidates: run a predefined Yahoo screen or a custom query.

        Each row has symbol, name, price, change %, volume, 3-month average volume, market cap
        and exchange. `total` is how many securities match in all.
        """
        key = {
            "tool": "screen_securities",
            "preset": preset,
            "query": query,
            "security_type": security_type,
            "sort_field": sort_field,
            "ascending": ascending,
            "count": count,
        }
        return context.answer(
            "screen",
            key,
            lambda: build_screen(
                context.gateway, preset, query, security_type, sort_field, ascending, count
            ),
            response_format,
        )

    @server.tool(title="Get sector or industry", annotations=READ_ONLY)
    def get_sector_industry(
        kind: Annotated[SectorKind, Field(description="'sector' or 'industry'.")],
        key: Annotated[
            str,
            Field(min_length=1, max_length=60, description=_KEY_DESCRIPTION),
        ],
        response_format: ResponseFormatParam = "concise",
    ) -> SectorIndustryResult:
        """Who leads a sector or industry: overview, top companies, top ETFs and funds.

        Sectors also list their industries; industries add top performers (YTD return,
        target price) and top growth companies.
        """
        normalized = key.strip().lower()
        return context.answer(
            "sector",
            {"tool": "get_sector_industry", "kind": kind, "key": normalized},
            lambda: build_sector_industry(context.gateway, kind, normalized),
            response_format,
        )
