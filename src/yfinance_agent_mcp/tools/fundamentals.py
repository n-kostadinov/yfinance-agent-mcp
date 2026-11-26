"""Financial statements, valuation and key ratios; and what analysts expect."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal

import pandas as pd
from mcp.server import MCPServer
from pydantic import Field, JsonValue

from yfinance_agent_mcp.errors import InvalidArgument
from yfinance_agent_mcp.gateway import MarketDataGateway
from yfinance_agent_mcp.models import AnalystResult, FundamentalsResult
from yfinance_agent_mcp.shaping import ResponseFormat, frame_to_records, snake_case, to_json_value
from yfinance_agent_mcp.tools.context import (
    READ_ONLY,
    ResponseFormatParam,
    SymbolParam,
    ToolContext,
    require_symbols,
    utc_now,
)

Statement = Literal["income", "balance", "cashflow", "valuation", "key_stats"]
Frequency = Literal["yearly", "quarterly", "trailing"]
# The line items a concise answer keeps; 'detailed' returns every line Yahoo has.
KEY_LINE_ITEMS: dict[str, tuple[str, ...]] = {
    "income": (
        "Total Revenue",
        "Gross Profit",
        "Operating Income",
        "Net Income",
        "Diluted EPS",
        "EBITDA",
        "Research And Development",
        "Operating Expense",
    ),
    "balance": (
        "Total Assets",
        "Total Liabilities Net Minority Interest",
        "Stockholders Equity",
        "Cash And Cash Equivalents",
        "Total Debt",
        "Net Debt",
        "Working Capital",
    ),
    "cashflow": (
        "Operating Cash Flow",
        "Capital Expenditure",
        "Free Cash Flow",
        "Repurchase Of Capital Stock",
        "Cash Dividends Paid",
    ),
}


def build_fundamentals(
    gateway: MarketDataGateway,
    symbol: str,
    statement: Statement,
    freq: Frequency,
    response_format: ResponseFormat,
) -> FundamentalsResult:
    result = FundamentalsResult(as_of=utc_now(), symbol=symbol, statement=statement)
    if statement == "key_stats":
        result.key_stats = gateway.key_stats(symbol)
        return result
    if statement == "valuation":
        result.periods = _period_records(gateway.valuation(symbol), line_items=None)
        return result
    if freq == "trailing" and statement == "balance":
        raise InvalidArgument(
            "freq 'trailing' (last twelve months) exists only for income and cashflow",
            ["yearly", "quarterly"],
        )
    frame = gateway.statement(symbol, statement, freq)
    line_items = None if response_format == "detailed" else KEY_LINE_ITEMS[statement]
    result.freq = freq
    result.periods = _period_records(frame, line_items)
    return result


def _period_records(
    frame: pd.DataFrame, line_items: Sequence[str] | None
) -> list[dict[str, JsonValue]]:
    """One record per period (column), with the line items (rows) as snake_case keys."""
    if line_items is not None:
        frame = frame.loc[[item for item in line_items if item in frame.index]]
    records: list[dict[str, JsonValue]] = []
    for column in frame.columns:
        values = frame[column]
        record: dict[str, JsonValue] = {"period": _period_label(column)}
        record.update({snake_case(item): to_json_value(value) for item, value in values.items()})  # type: ignore[misc]
        records.append(record)
    return records


def _period_label(column: object) -> str:
    return column.date().isoformat() if isinstance(column, pd.Timestamp) else str(column)


def build_analyst_view(
    gateway: MarketDataGateway, symbol: str, rating_changes: int
) -> AnalystResult:
    data = gateway.analyst(symbol)
    changes = data.rating_changes
    if changes is not None and not changes.empty:
        changes = changes.sort_index(ascending=False)
    return AnalystResult(
        as_of=utc_now(),
        symbol=symbol,
        price_targets={str(k): to_json_value(v) for k, v in data.price_targets.items()},  # type: ignore[misc]
        recommendations=_table(data.recommendations),
        rating_changes=_table(changes, limit=rating_changes),
        earnings_estimate=_table(data.earnings_estimate, index_name="period"),
        revenue_estimate=_table(data.revenue_estimate, index_name="period"),
        eps_trend=_table(data.eps_trend, index_name="period"),
        eps_revisions=_table(data.eps_revisions, index_name="period"),
        growth_estimates=_table(data.growth_estimates, index_name="period"),
    )


def _table(
    frame: pd.DataFrame | None, *, limit: int | None = None, index_name: str | None = None
) -> list[dict[str, JsonValue]]:
    if frame is None or frame.empty:
        return []
    name = index_name or (snake_case(frame.index.name) if frame.index.name else None)
    page = frame_to_records(frame.rename(columns=snake_case), index_name=name, limit=limit)
    return page.records  # type: ignore[return-value]


def register(server: MCPServer, context: ToolContext) -> None:
    @server.tool(title="Get fundamentals", annotations=READ_ONLY)
    def get_fundamentals(
        symbol: SymbolParam,
        statement: Annotated[
            Statement,
            Field(
                description="income, balance (sheet), cashflow, valuation (history of market "
                "cap, P/E, EV/EBITDA...) or key_stats (margins, growth, debt, ownership)."
            ),
        ] = "income",
        freq: Annotated[
            Frequency,
            Field(description="Statement periods; 'trailing' = last twelve months (not balance)."),
        ] = "quarterly",
        response_format: ResponseFormatParam = "concise",
    ) -> FundamentalsResult:
        """Financial statements, valuation history or key ratios for one symbol.

        Statements come as one record per period, newest first. 'concise' keeps the key line
        items (revenue, net income, EPS, cash flow, debt...); 'detailed' returns every line.
        """
        checked = require_symbols([symbol])[0]
        return context.answer(
            "fundamentals",
            {"tool": "get_fundamentals", "symbol": checked, "statement": statement, "freq": freq},
            lambda: build_fundamentals(context.gateway, checked, statement, freq, response_format),
            response_format,
        )

    @server.tool(title="Get analyst view", annotations=READ_ONLY)
    def get_analyst_view(
        symbol: SymbolParam,
        rating_changes: Annotated[
            int, Field(ge=1, le=50, description="How many recent upgrades/downgrades to show.")
        ] = 10,
        response_format: ResponseFormatParam = "concise",
    ) -> AnalystResult:
        """What analysts expect for one symbol: price targets, buy/hold/sell counts, recent
        rating changes, EPS and revenue estimates, estimate trends and revisions, growth."""
        checked = require_symbols([symbol])[0]
        return context.answer(
            "analysts",
            {"tool": "get_analyst_view", "symbol": checked, "rating_changes": rating_changes},
            lambda: build_analyst_view(context.gateway, checked, rating_changes),
            response_format,
        )
