"""Summary statistics an agent needs from a price history: returns, trend, momentum, risk.

Input bars are a DataFrame with ``open, high, low, close, volume`` columns and an ascending,
timezone-aware index (the gateway normalizes yfinance output to this shape).
"""

from __future__ import annotations

from datetime import timedelta
from typing import cast

import numpy as np
import pandas as pd

from yfinance_agent_mcp.models import PriceSummary
from yfinance_agent_mcp.shaping import iso_utc, round_price

_CHANGE_WINDOWS = {
    "1d": timedelta(days=1),
    "5d": timedelta(days=5),
    "1mo": timedelta(days=30),
    "3mo": timedelta(days=91),
    "6mo": timedelta(days=182),
    "1y": timedelta(days=365),
}
_SMA_LENGTHS = (20, 50, 200)
_WILDER_PERIOD = 14
_VOLUME_LOOKBACK = 20


def summarize_prices(bars: pd.DataFrame) -> PriceSummary:
    """Compute the price summary; any statistic without enough bars is ``None``."""
    if bars.empty:
        return PriceSummary(bars=0)
    close = _column(bars, "close")
    last_time = cast(pd.Timestamp, bars.index[-1])
    last = float(close.iloc[-1])
    atr = _wilder_atr(bars)
    year = bars.loc[bars.index >= last_time - timedelta(days=365)]
    high, low = float(_column(year, "high").max()), float(_column(year, "low").min())
    return PriceSummary(
        bars=len(bars),
        last_close=round_price(last),
        last_bar_time=iso_utc(last_time),
        **_changes(close, last, last_time),
        **_moving_averages(close, last),
        rsi_14=_wilder_rsi(close.to_numpy()),
        atr_14=round_price(atr),
        atr_pct=None if atr is None else round(atr / last * 100, 2),
        high_52w=round_price(high),
        low_52w=round_price(low),
        from_high_52w_pct=_change_pct(last, high),
        from_low_52w_pct=_change_pct(last, low),
        volume_vs_avg_20=_volume_ratio(_column(bars, "volume")),
    )


def _column(bars: pd.DataFrame, name: str) -> pd.Series:
    return cast(pd.Series, bars[name]).astype(float)


def _changes(close: pd.Series, last: float, last_time: pd.Timestamp) -> dict[str, float | None]:
    changes = {
        f"change_{name}_pct": _change_pct(last, _close_at_or_before(close, last_time - window))
        for name, window in _CHANGE_WINDOWS.items()
    }
    year_start = pd.Timestamp(year=last_time.year, month=1, day=1, tz=last_time.tz)
    before_year = close.loc[close.index < year_start]
    previous_year_close = float(before_year.iloc[-1]) if len(before_year) else None
    changes["change_ytd_pct"] = _change_pct(last, previous_year_close)
    return changes


def _moving_averages(close: pd.Series, last: float) -> dict[str, float | None]:
    averages: dict[str, float | None] = {}
    for length in _SMA_LENGTHS:
        sma = float(close.iloc[-length:].mean()) if len(close) >= length else None
        averages[f"sma_{length}"] = round_price(sma)
        averages[f"close_vs_sma_{length}_pct"] = _change_pct(last, sma)
    return averages


def _close_at_or_before(close: pd.Series, moment: pd.Timestamp) -> float | None:
    earlier = close.loc[:moment]
    return float(earlier.iloc[-1]) if len(earlier) else None


def _wilder_rsi(closes: np.ndarray) -> float | None:
    if len(closes) <= _WILDER_PERIOD:
        return None
    changes = np.diff(closes)
    gains, losses = np.clip(changes, 0, None), np.clip(-changes, 0, None)
    avg_gain = gains[:_WILDER_PERIOD].mean()
    avg_loss = losses[:_WILDER_PERIOD].mean()
    for gain, loss in zip(gains[_WILDER_PERIOD:], losses[_WILDER_PERIOD:], strict=True):
        avg_gain = (avg_gain * (_WILDER_PERIOD - 1) + gain) / _WILDER_PERIOD
        avg_loss = (avg_loss * (_WILDER_PERIOD - 1) + loss) / _WILDER_PERIOD
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else None  # flat prices have no momentum to measure
    return round(100 - 100 / (1 + avg_gain / avg_loss), 2)


def _wilder_atr(bars: pd.DataFrame) -> float | None:
    if len(bars) < _WILDER_PERIOD:
        return None
    high, low = bars["high"].to_numpy(float), bars["low"].to_numpy(float)
    previous_close = bars["close"].to_numpy(float)[:-1]
    true_range = high - low
    true_range[1:] = np.maximum.reduce(
        [true_range[1:], np.abs(high[1:] - previous_close), np.abs(low[1:] - previous_close)]
    )
    atr = true_range[:_WILDER_PERIOD].mean()
    for value in true_range[_WILDER_PERIOD:]:
        atr = (atr * (_WILDER_PERIOD - 1) + value) / _WILDER_PERIOD
    return float(atr)


def _volume_ratio(volume: pd.Series) -> float | None:
    if len(volume) <= _VOLUME_LOOKBACK:
        return None
    average = volume.iloc[-_VOLUME_LOOKBACK - 1 : -1].mean()
    return round(float(volume.iloc[-1] / average), 2) if average > 0 else None


def _change_pct(current: float | None, reference: float | None) -> float | None:
    if current is None or reference is None or reference == 0:
        return None
    return round((current / reference - 1) * 100, 2)
