from __future__ import annotations

import json
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
import pytest
from pydantic import BaseModel

from yfinance_agent_mcp.models import Envelope
from yfinance_agent_mcp.shaping import (
    fit_to_budget,
    frame_to_records,
    snake_case,
    to_json_value,
    truncate_text,
)


@pytest.mark.parametrize("missing", [None, float("nan"), float("inf"), pd.NA, pd.NaT, np.nan])
def test_missing_numbers_become_null(missing: object) -> None:
    assert to_json_value(missing) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (pd.Timestamp("2026-11-24 16:00", tz="America/New_York"), "2026-11-24T21:00:00Z"),
        (datetime(2026, 11, 24, 21, 0), "2026-11-24T21:00:00Z"),
        (datetime(2026, 11, 24, 21, 0, tzinfo=UTC), "2026-11-24T21:00:00Z"),
        (date(2026, 11, 24), "2026-11-24"),
    ],
)
def test_timestamps_become_utc_iso_8601(value: object, expected: str) -> None:
    assert to_json_value(value) == expected


def test_numpy_scalars_become_plain_python_values() -> None:
    values = [
        to_json_value(np.int64(5)),
        to_json_value(np.float64(1.5)),
        to_json_value(np.bool_(1)),
    ]

    assert values == [5, 1.5, True]
    assert [type(v) for v in values] == [int, float, bool]


def test_nested_containers_are_converted_recursively() -> None:
    value = {"when": pd.Timestamp("2026-01-02", tz="UTC"), "items": [np.int64(1), float("nan")]}

    assert to_json_value(value) == {"when": "2026-01-02T00:00:00Z", "items": [1, None]}


def test_truncate_text_shortens_long_text_with_an_ellipsis() -> None:
    assert truncate_text("abcdefgh", 5) == "abcd…"
    assert truncate_text("abc", 5) == "abc"
    assert truncate_text(None, 5) is None


def make_frame(rows: int) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=rows, freq="D", tz="UTC", name="Date")
    return pd.DataFrame({"close": range(rows), "volume": [100] * rows}, index=index)


def test_frame_records_include_the_index_and_only_the_selected_columns() -> None:
    page = frame_to_records(make_frame(2), index_name="date", columns=["close"])

    assert page.records == [
        {"date": "2026-01-01T00:00:00Z", "close": 0},
        {"date": "2026-01-02T00:00:00Z", "close": 1},
    ]
    assert (page.total, page.truncated, page.next_offset) == (2, False, None)


def test_frame_window_reports_truncation_and_the_next_offset() -> None:
    frame = make_frame(10)

    middle = frame_to_records(frame, limit=3, offset=2)
    last = frame_to_records(frame, limit=3, offset=8)

    assert [r["close"] for r in middle.records] == [2, 3, 4]
    assert (middle.truncated, middle.next_offset) == (True, 5)
    assert [r["close"] for r in last.records] == [8, 9]
    assert (last.truncated, last.next_offset) == (False, None)


class Row(BaseModel):
    text: str


class Listing(Envelope):
    small: list[Row]
    large: list[Row]


def test_fit_to_budget_trims_the_largest_list_and_flags_truncation() -> None:
    result = Listing(
        as_of=datetime(2026, 11, 24, tzinfo=UTC),
        small=[Row(text="keep")],
        large=[Row(text="x" * 100) for _ in range(500)],
    )

    fitted = fit_to_budget(result, 5_000)

    assert len(fitted.model_dump_json()) <= 5_000
    assert fitted.small == [Row(text="keep")]
    assert 0 < len(fitted.large) < 500
    assert fitted.truncated is True
    assert any("large" in warning for warning in fitted.warnings)


def test_fit_to_budget_leaves_a_small_result_untouched() -> None:
    result = Listing(as_of=datetime(2026, 11, 24, tzinfo=UTC), small=[], large=[Row(text="a")])

    fitted = fit_to_budget(result, 5_000)

    assert json.loads(fitted.model_dump_json()) == json.loads(result.model_dump_json())
    assert fitted.truncated is False


@pytest.mark.parametrize(
    ("label", "key"),
    [
        ("Surprise(%)", "surprise_pct"),
        ("Event Start Date", "event_start_date"),
        ("Ex-Dividend Date", "ex_dividend_date"),
        ("strongBuy", "strong_buy"),
        ("numberOfAnalysts", "number_of_analysts"),
        ("Trailing P/E", "trailing_p_e"),
        ("EBITDA", "ebitda"),
    ],
)
def test_yahoo_labels_become_snake_case_keys(label: str, key: str) -> None:
    assert snake_case(label) == key
