"""Everything else yfinance knows about a ticker: holders, insiders, dividends, filings, funds."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Annotated, Literal

import pandas as pd
from mcp.server import MCPServer
from pydantic import Field, JsonValue

from yfinance_agent_mcp.errors import InvalidArgument
from yfinance_agent_mcp.gateway import TICKER_DATASETS, MarketDataGateway
from yfinance_agent_mcp.models import TickerDatasetResult
from yfinance_agent_mcp.shaping import (
    budget_for,
    frame_to_records,
    snake_case,
    to_json_value,
    truncate_text,
)
from yfinance_agent_mcp.tools.context import (
    READ_ONLY,
    ResponseFormatParam,
    SymbolParam,
    ToolContext,
    require_symbols,
    utc_now,
)

Dataset = Literal[
    "info",
    "major_holders",
    "institutional_holders",
    "mutualfund_holders",
    "insider_purchases",
    "insider_transactions",
    "insider_roster_holders",
    "dividends",
    "splits",
    "capital_gains",
    "actions",
    "isin",
    "sustainability",
    "sec_filings",
    "earnings_history",
    "history_metadata",
    "fund_description",
    "fund_overview",
    "fund_operations",
    "fund_asset_classes",
    "fund_top_holdings",
    "fund_equity_holdings",
    "fund_bond_holdings",
    "fund_bond_ratings",
    "fund_sector_weightings",
]
_ENVELOPE_CHARS = 1_000


def build_ticker_dataset(
    gateway: MarketDataGateway,
    symbol: str,
    dataset: str,
    limit: int,
    offset: int,
    columns: Sequence[str] | None,
    budget: int,
) -> TickerDatasetResult:
    """Fetch one allowlisted dataset: tables come back as paged rows, anything else as data."""
    if dataset not in TICKER_DATASETS:
        raise InvalidArgument(f"unknown dataset {dataset!r}", list(TICKER_DATASETS))
    value = gateway.ticker_dataset(symbol, dataset)
    result = TickerDatasetResult(as_of=utc_now(), symbol=symbol, dataset=dataset)
    if isinstance(value, pd.Series):
        value = value.to_frame(name=value.name or dataset)
    if isinstance(value, pd.DataFrame):
        _fill_table(result, _readable(value), limit, offset, columns)
    elif isinstance(value, list):
        window = value[offset : offset + limit]
        result.data = to_json_value(window)
        result.total_rows = len(value)
        result.truncated = offset + limit < len(value)
        result.next_offset = offset + limit if result.truncated else None
    else:
        _fill_data(result, to_json_value(value), budget)
    return result


def _fill_data(result: TickerDatasetResult, data: JsonValue, budget: int) -> None:
    """Keep dict and text data within the budget: leading keys first, text cut short."""
    room = budget - _ENVELOPE_CHARS
    if len(json.dumps(data)) <= room:
        result.data = data
        return
    if isinstance(data, dict):
        kept: dict[str, JsonValue] = {}
        used = 2
        for key, value in data.items():
            used += len(json.dumps({key: value})) - 1
            if used > room:
                break
            kept[key] = value
        result.data = kept
        result.warnings.append(f"Kept the first {len(kept)} of {len(data)} keys to fit the budget.")
    else:
        result.data = truncate_text(str(data), room)
        result.warnings.append("Text cut short to fit the response budget.")
    result.truncated = True


def _readable(table: pd.DataFrame) -> pd.DataFrame:
    """snake_case columns; time-indexed tables newest first, since agents want recent rows."""
    readable = table.rename(columns=snake_case)
    if isinstance(readable.index, pd.DatetimeIndex):
        readable = readable.sort_index(ascending=False)
    return readable


def _fill_table(
    result: TickerDatasetResult,
    table: pd.DataFrame,
    limit: int,
    offset: int,
    columns: Sequence[str] | None,
) -> None:
    result.columns = [str(column) for column in table.columns]
    if columns:
        unknown = [column for column in columns if column not in result.columns]
        if unknown:
            raise InvalidArgument(f"unknown columns {', '.join(unknown)}", result.columns)
    index_name = None
    if not isinstance(table.index, pd.RangeIndex):
        index_name = snake_case(table.index.name) if table.index.name else "key"
    page = frame_to_records(
        table,
        index_name=index_name,
        columns=list(columns) if columns else None,
        limit=limit,
        offset=offset,
    )
    result.rows = page.records  # type: ignore[assignment]
    result.total_rows = page.total
    result.truncated = page.truncated
    result.next_offset = page.next_offset
    if page.total == 0:
        result.warnings.append(f"Yahoo has no {result.dataset} rows for {result.symbol}.")


def register(server: MCPServer, context: ToolContext) -> None:
    @server.tool(title="Get ticker dataset", annotations=READ_ONLY)
    def get_ticker_dataset(
        symbol: SymbolParam,
        dataset: Annotated[
            Dataset,
            Field(
                description="Holders and insiders, dividends/splits/actions, ISIN, ESG, SEC "
                "filings, earnings history, chart metadata, the raw quote summary ('info'), "
                "or an ETF/fund's overview, holdings and weightings (fund_*)."
            ),
        ],
        limit: Annotated[int, Field(ge=1, le=25, description="Rows per page.")] = 25,
        offset: Annotated[int, Field(ge=0, description="First row; use `next_offset`.")] = 0,
        columns: Annotated[
            list[str] | None,
            Field(description="Keep only these columns (see `columns` in a first answer)."),
        ] = None,
        response_format: ResponseFormatParam = "concise",
    ) -> TickerDatasetResult:
        """Any other yfinance data for one symbol, from an allowlist of datasets.

        Tables come back as paged `rows` (time-indexed ones newest first); text, dict and
        list datasets come back as `data`.
        """
        checked = require_symbols([symbol])[0]
        key = {
            "tool": "get_ticker_dataset",
            "symbol": checked,
            "dataset": dataset,
            "limit": limit,
            "offset": offset,
            "columns": columns,
        }
        return context.answer(
            "datasets",
            key,
            lambda: build_ticker_dataset(
                context.gateway,
                checked,
                dataset,
                limit,
                offset,
                columns,
                budget_for(response_format),
            ),
            response_format,
        )
