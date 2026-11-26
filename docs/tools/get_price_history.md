---
title: get_price_history - price history with RSI, ATR and moving averages
description: The get_price_history tool returns bars plus returns, SMA 20/50/200, RSI 14, ATR 14 and the 52-week range for up to 10 symbols.
---

# get_price_history

Price history for up to 10 symbols, with the indicators an agent would otherwise compute
itself: changes over 1 day to 1 year and year to date, simple moving averages, Wilder RSI and
ATR, the 52-week range and volume versus average. Prices are adjusted for splits and
dividends.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbols` | list of 1-10 strings | required | Yahoo symbols. |
| `period` | `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max` | `6mo` | How far back; ignored when `start` is given. |
| `interval` | `1m`, `2m`, `5m`, `15m`, `30m`, `60m`, `90m`, `1h`, `1d`, `5d`, `1wk`, `1mo`, `3mo` | `1d` | Bar length. |
| `start` | date `YYYY-MM-DD` | none | First day; overrides `period`. |
| `end` | date `YYYY-MM-DD` | none | Day after the last bar; needs `start`. |
| `mode` | `summary` or `bars` | `summary` | `summary` adds the indicators to the latest bars; `bars` returns bars only. |
| `bars` | integer, 1-500 | `20` | How many of the most recent bars to return. |
| `response_format` | `concise` or `detailed` | `concise` | Size budget: 20,000 or 80,000 characters. |

### Ranges Yahoo can serve

- Intraday intervals (`1m` to `1h`) cover the last 60 days: use `period` `1d`, `5d` or `1mo`,
  or a `start` within 60 days.
- `1m` bars: at most 7 days per request, within the last 30 days (`period` `1d` or `5d`).
- Other requests are rejected with `invalid_argument` before Yahoo is asked.

## Returns

| Field | Description |
|---|---|
| `period`, `start`, `end`, `interval`, `mode` | The request as served. |
| `prices` | Per symbol: `symbol`, `currency`, `exchange`, `interval`, `bar_count`, `first_bar_time`, `last_bar_time`, `summary`, `bars`. |
| `errors` | Symbols without data. |

`summary` fields: `last_close`, `change_1d_pct`, `change_5d_pct`, `change_1mo_pct`,
`change_3mo_pct`, `change_6mo_pct`, `change_1y_pct`, `change_ytd_pct`, `sma_20`, `sma_50`,
`sma_200`, `close_vs_sma_20_pct`, `close_vs_sma_50_pct`, `close_vs_sma_200_pct`, `rsi_14`,
`atr_14`, `atr_pct`, `high_52w`, `low_52w`, `from_high_52w_pct`, `from_low_52w_pct`,
`volume_vs_avg_20`. Any statistic without enough bars is `null` (for example `sma_200` needs
200 bars). Changes compare with the close at or before the same calendar time earlier.

`bars` entries: `time` (bar start, UTC), `open`, `high`, `low`, `close`, `volume`, oldest
first.

## Example

```json
{ "symbols": ["NVDA"], "period": "1y" }
```

```json
{
  "as_of": "2026-11-24T15:30:12Z",
  "interval": "1d",
  "mode": "summary",
  "prices": [
    {
      "symbol": "NVDA",
      "bar_count": 251,
      "last_bar_time": "2026-11-24T14:30:00Z",
      "summary": {
        "last_close": 165.05, "change_1d_pct": 2.1, "change_1y_pct": -7.18,
        "sma_50": 171.2, "sma_200": 158.4, "rsi_14": 47.3, "atr_14": 6.12, "atr_pct": 3.71,
        "high_52w": 212.2, "low_52w": 120.1, "volume_vs_avg_20": 1.8
      },
      "bars": [
        { "time": "2026-11-21T14:30:00Z", "open": 160.1, "high": 166.0, "low": 158.9, "close": 161.7, "volume": 312000000.0 }
      ]
    }
  ],
  "errors": []
}
```

## Limits and cost

- One Yahoo request per symbol; cached for 30 seconds for intraday intervals and 5 minutes
  for daily and longer (categories `history_intraday`, `history_daily`).
- Asking for many bars and symbols at once returns fewer bars per symbol, so the answer fits
  the budget; `warnings` says so.
