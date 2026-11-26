from __future__ import annotations

import pandas as pd
import pytest

from yfinance_agent_mcp.indicators import summarize_prices


def daily_bars(
    closes: list[float],
    *,
    start: str = "2025-01-01",
    spread: float = 0.0,
    volumes: list[float] | None = None,
) -> pd.DataFrame:
    """Daily bars ending on the last close; high/low sit ``spread`` above/below the close."""
    index = pd.date_range(start, periods=len(closes), freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + spread for c in closes],
            "low": [c - spread for c in closes],
            "close": closes,
            "volume": volumes or [1_000.0] * len(closes),
        },
        index=index,
    )


def test_moving_averages_are_simple_means_of_the_latest_closes() -> None:
    summary = summarize_prices(daily_bars([float(c) for c in range(1, 201)]))

    assert (summary.sma_20, summary.sma_50, summary.sma_200) == (190.5, 175.5, 100.5)
    assert summary.close_vs_sma_200_pct == pytest.approx(99.0, abs=0.01)


@pytest.mark.parametrize(
    ("closes", "expected_rsi"),
    [
        ([float(c) for c in range(1, 31)], 100.0),
        ([float(c) for c in range(30, 0, -1)], 0.0),
        ([10.0, 11.0] * 7 + [10.0], 50.0),
    ],
)
def test_rsi_reflects_the_balance_of_gains_and_losses(
    closes: list[float], expected_rsi: float
) -> None:
    assert summarize_prices(daily_bars(closes)).rsi_14 == expected_rsi


def test_rsi_matches_the_published_wilder_example() -> None:
    # StockCharts ChartSchool RSI worksheet: 33 closes, RSI(14) after the last close is 37.77.
    closes = [
        44.3389, 44.0902, 44.1497, 43.6124, 44.3278, 44.8264, 45.0955, 45.4245, 45.8433,
        46.0826, 45.8931, 46.0328, 45.6140, 46.2820, 46.2820, 46.0028, 46.0328, 46.4116,
        46.2222, 45.6439, 46.2122, 46.2521, 45.7137, 46.4515, 45.7835, 45.3548, 44.0288,
        44.1783, 44.2181, 44.5672, 43.4205, 42.6628, 43.1314,
    ]  # fmt: skip

    assert summarize_prices(daily_bars(closes)).rsi_14 == pytest.approx(37.77, abs=0.01)


def test_atr_equals_a_constant_daily_range() -> None:
    summary = summarize_prices(daily_bars([100.0] * 30, spread=1.0))

    assert summary.atr_14 == 2.0
    assert summary.atr_pct == 2.0


def test_changes_compare_with_the_close_at_or_before_each_calendar_window() -> None:
    closes = [100.0 + day for day in range(400)]  # 2025-01-01 .. 2026-02-04

    summary = summarize_prices(daily_bars(closes))

    assert summary.last_close == 499.0
    assert summary.last_bar_time == "2026-02-04T00:00:00Z"
    assert summary.change_1d_pct == pytest.approx((499 / 498 - 1) * 100, abs=0.01)
    assert summary.change_1y_pct == pytest.approx((499 / 134 - 1) * 100, abs=0.01)
    assert summary.change_ytd_pct == pytest.approx((499 / 464 - 1) * 100, abs=0.01)


def test_52_week_range_and_volume_ratio() -> None:
    closes = [50.0] * 30 + [80.0] + [60.0] * 9
    volumes = [100.0] * 39 + [150.0]

    summary = summarize_prices(daily_bars(closes, volumes=volumes))

    assert (summary.high_52w, summary.low_52w) == (80.0, 50.0)
    assert summary.from_high_52w_pct == -25.0
    assert summary.from_low_52w_pct == 20.0
    assert summary.volume_vs_avg_20 == 1.5


def test_windows_without_enough_bars_are_null() -> None:
    summary = summarize_prices(daily_bars([10.0, 11.0, 12.0]))

    assert summary.bars == 3
    assert summary.sma_20 is None
    assert summary.rsi_14 is None
    assert summary.atr_14 is None
    assert summary.change_1y_pct is None
    assert summary.volume_vs_avg_20 is None


def test_empty_history_has_no_values() -> None:
    summary = summarize_prices(daily_bars([]))

    assert summary.bars == 0
    assert summary.last_close is None
    assert summary.last_bar_time is None
