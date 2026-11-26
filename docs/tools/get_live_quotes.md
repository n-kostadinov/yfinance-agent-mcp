---
title: get_live_quotes - real-time prices from Yahoo's streaming feed
description: The get_live_quotes tool returns the latest streamed price of up to 25 symbols from Yahoo's websocket feed, with the age of each tick.
---

# get_live_quotes

The price right now, from Yahoo's streaming feed, for up to 25 symbols.

The server keeps one websocket connection to Yahoo. The first call subscribes the symbols
and waits up to `wait_seconds` for their first ticks; later calls answer at once with the
latest tick of each symbol and its age. Symbols nobody asks for in 10 minutes are
unsubscribed, and a dropped connection is reopened on the next call.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbols` | list of 1-25 strings | required | Yahoo symbols. |
| `wait_seconds` | number, 0-10 | `3` | How long to wait for symbols without a tick yet. |
| `response_format` | `concise` or `detailed` | `concise` | Size budget: 20,000 or 80,000 characters. |

## Returns

| Field | Description |
|---|---|
| `ticks` | Per symbol: `symbol`, `price`, `change_pct`, `day_volume`, `market_hours`, `exchange_time` (the exchange's time of the tick, UTC), `received_at`, `age_seconds`. |
| `missing` | Symbols without a tick yet: the market is closed, the symbol is illiquid, or it is unknown. |

A quiet symbol is not an error. [`get_quotes`](get_quotes.md) has its last price.

## Example

```json
{ "symbols": ["BTC-USD", "AAPL"], "wait_seconds": 5 }
```

```json
{
  "as_of": "2026-11-24T23:10:04Z",
  "ticks": [
    { "symbol": "BTC-USD", "price": 87012.5, "change_pct": 1.12, "day_volume": 43823312896.0, "market_hours": "1", "exchange_time": "2026-11-24T23:10:01Z", "received_at": "2026-11-24T23:10:02Z", "age_seconds": 2.0 }
  ],
  "missing": ["AAPL"],
  "warnings": ["No tick within 5 s for AAPL: the market may be closed or the symbol illiquid or unknown; get_quotes has the last price."]
}
```

## Limits and cost

- No HTTP requests: ticks arrive over one shared websocket. Answers are not cached; the
  stream itself keeps the latest tick.
- Crypto streams around the clock; stocks tick only while their market is open.
