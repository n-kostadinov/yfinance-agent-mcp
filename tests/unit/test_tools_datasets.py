from __future__ import annotations

from datetime import date
from typing import get_args

import pandas as pd
import pytest
import yfinance as yf
from yfinance.scrapers.funds import FundsData

from tests.fakes import FakeGateway
from yfinance_agent_mcp.errors import InvalidArgument
from yfinance_agent_mcp.gateway import TICKER_DATASETS
from yfinance_agent_mcp.shaping import to_json_value
from yfinance_agent_mcp.tools.datasets import Dataset, build_ticker_dataset


def test_every_allowlisted_dataset_is_a_property_of_installed_yfinance() -> None:
    for path in TICKER_DATASETS.values():
        owner = yf.Ticker if len(path) == 1 else FundsData
        assert isinstance(getattr(yf.Ticker, path[0], None), property), path
        assert isinstance(getattr(owner, path[-1], None), property), path


def test_tool_offers_exactly_the_allowlisted_datasets() -> None:
    assert set(get_args(Dataset)) == set(TICKER_DATASETS)


def gateway_with(dataset: str, value: object) -> FakeGateway:
    gateway = FakeGateway()
    gateway.datasets[("AAPL", dataset)] = value
    return gateway


def test_series_dataset_becomes_dated_rows_newest_first() -> None:
    dividends = pd.Series(
        [0.25, 0.26],
        index=pd.DatetimeIndex(["2026-05-12", "2026-08-11"], tz="America/New_York", name="Date"),
        name="Dividends",
    )

    result = build_ticker_dataset(
        gateway_with("dividends", dividends), "AAPL", "dividends", 25, 0, None, 20_000
    )

    assert result.rows == [
        {"date": "2026-08-11T04:00:00Z", "dividends": 0.26},
        {"date": "2026-05-12T04:00:00Z", "dividends": 0.25},
    ]
    assert result.columns == ["dividends"]


def holders(rows: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Holder": [f"Fund {n}" for n in range(rows)],
            "pctHeld": [0.01] * rows,
            "Shares": [1_000] * rows,
        }
    )


def test_tables_are_paged_with_limit_and_offset() -> None:
    gateway = gateway_with("institutional_holders", holders(60))

    first = build_ticker_dataset(gateway, "AAPL", "institutional_holders", 25, 0, None, 20_000)
    last = build_ticker_dataset(gateway, "AAPL", "institutional_holders", 25, 50, None, 20_000)

    assert (len(first.rows), first.total_rows, first.truncated, first.next_offset) == (
        25,
        60,
        True,
        25,
    )
    assert (len(last.rows), last.truncated, last.next_offset) == (10, False, None)
    assert first.rows[0] == {"holder": "Fund 0", "pct_held": 0.01, "shares": 1_000}


def test_column_selection_keeps_only_the_named_columns() -> None:
    gateway = gateway_with("institutional_holders", holders(2))

    result = build_ticker_dataset(
        gateway, "AAPL", "institutional_holders", 25, 0, ["holder"], 20_000
    )

    assert result.rows == [{"holder": "Fund 0"}, {"holder": "Fund 1"}]


def test_unknown_column_lists_the_available_ones() -> None:
    gateway = gateway_with("institutional_holders", holders(2))

    with pytest.raises(InvalidArgument, match="holder, pct_held, shares"):
        build_ticker_dataset(gateway, "AAPL", "institutional_holders", 25, 0, ["owner"], 20_000)


def test_unknown_dataset_lists_the_valid_ones() -> None:
    with pytest.raises(InvalidArgument, match="major_holders"):
        build_ticker_dataset(FakeGateway(), "AAPL", "holders", 25, 0, None, 20_000)


@pytest.mark.parametrize(
    ("dataset", "value"),
    [
        ("isin", "US0378331005"),
        ("fund_overview", {"categoryName": "Large Blend", "family": "State Street"}),
    ],
)
def test_text_and_dict_datasets_come_back_as_data(dataset: str, value: object) -> None:
    result = build_ticker_dataset(
        gateway_with(dataset, value), "AAPL", dataset, 25, 0, None, 20_000
    )

    assert result.data == value
    assert result.rows == []


def test_list_dataset_is_paged() -> None:
    filings = [{"date": date(2026, 11, 9 - n), "type": "8-K"} for n in range(5)]

    result = build_ticker_dataset(
        gateway_with("sec_filings", filings), "AAPL", "sec_filings", 2, 0, None, 20_000
    )

    assert result.data == [
        {"date": "2026-11-09", "type": "8-K"},
        {"date": "2026-11-08", "type": "8-K"},
    ]
    assert (result.total_rows, result.truncated, result.next_offset) == (5, True, 2)


def test_nested_tables_in_a_dict_become_json() -> None:
    value = {"tradingPeriods": pd.DataFrame({"start": [1]}, index=pd.Index(["d1"], name="day"))}

    assert to_json_value(value) == {"tradingPeriods": [{"day": "d1", "start": 1}]}


def test_oversized_dict_data_keeps_the_leading_keys_that_fit() -> None:
    info = {f"field_{n}": "x" * 100 for n in range(1_000)}

    result = build_ticker_dataset(gateway_with("info", info), "AAPL", "info", 25, 0, None, 20_000)

    assert isinstance(result.data, dict)
    assert list(result.data)[:2] == ["field_0", "field_1"]
    assert len(result.model_dump_json()) <= 20_000
    assert result.truncated is True
