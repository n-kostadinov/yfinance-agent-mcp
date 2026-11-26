---
title: get_quotes - latest prices, daily change and data freshness
description: The get_quotes tool returns price, change, day range, volume and 52-week range for up to 25 Yahoo symbols, with market state, quote source and delay.
---

# get_quotes

Latest price, change versus the previous close, day range, volume and 52-week range for up
to 25 symbols, with the fields an agent needs to judge how current each price is.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbols` | list of 1-25 strings | required | Yahoo symbols, e.g. `["AAPL", "SAP.DE", "BTC-USD", "^GSPC"]`. Case and duplicates do not matter. |
| `include_details` | boolean | `false` | Add Yahoo's market state, quote source and delay, plus market cap, P/E, dividend yield, beta, moving averages, pre/post-market prices, bid/ask, sector and industry. |
| `response_format` | `concise` or `detailed` | `concise` | Size budget: 20,000 or 80,000 characters. |

## Returns

| Field | Description |
|---|---|
| `quotes` | One entry per symbol with data: `symbol`, `name`, `price`, `change_pct`, `previous_close`, `day_high`, `day_low`, `volume`, `high_52w`, `low_52w`, `currency`, `exchange`, `market_state`, `market_time`, `quote_source`, `delay_min`, `details`. |
| `errors` | Symbols without data: `symbol`, `error` code and `message`. |

Freshness fields:

- `market_time`: time of the last regular-session price, UTC.
- `market_state`: `PRE`, `REGULAR`, `POST` or `CLOSED`. Without `include_details` it is
  derived from the exchange's trading hours; with it, Yahoo's own state (which can also be
  `PREPRE` or `POSTPOST`).
- `delay_min` and `quote_source`: only with `include_details`. `delay_min: 0` is real time;
  many European exchanges report `15`.

When any quote is delayed, `warnings` names the symbols.

## Example

```json
{ "symbols": ["AAPL", "SAP.DE", "BTC-USD"], "include_details": true }
```

```json
{
  "as_of": "2026-11-24T15:30:12Z",
  "warnings": ["Delayed by up to 15 min: AAPL, SAP.DE."],
  "quotes": [
    {
      "symbol": "BTC-USD",
      "name": "Bitcoin USD",
      "price": 87012.5,
      "change_pct": 1.12,
      "currency": "USD",
      "market_state": "REGULAR",
      "market_time": "2026-11-24T15:29:00Z",
      "quote_source": "CoinMarketCap",
      "delay_min": 0,
      "details": { "market_cap": 1720000000000.0, "average_volume": 41200000000.0 }
    }
  ],
  "errors": []
}
```

## Limits and cost

- One Yahoo request per symbol, plus three more per symbol with `include_details`.
- Cached for 15 seconds (category `quotes`).
- After a rate limit the remaining symbols are reported in `errors` as `rate_limited`
  rather than requested.
- For the price this second, use [`get_live_quotes`](get_live_quotes.md).
