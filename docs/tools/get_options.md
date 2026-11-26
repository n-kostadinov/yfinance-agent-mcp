---
title: get_options - option chain around the price, implied volatility
description: The get_options tool returns calls and puts around the current price for one expiration, with bid, ask, volume, open interest and implied volatility.
---

# get_options

Calls and puts around the current price for one expiration, plus the list of every
expiration.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | string | required | One Yahoo symbol with listed options. |
| `expiry` | date `YYYY-MM-DD` | nearest | Expiration to show; must be one of `expirations`. |
| `strikes_each_side` | integer, 1-25 | `10` | Strikes below and at or above the current price. |
| `response_format` | `concise` or `detailed` | `concise` | Size budget: 20,000 or 80,000 characters. |

## Returns

| Field | Description |
|---|---|
| `symbol`, `expiry` | The chain shown. |
| `expirations` | Every listed expiration, nearest first. |
| `underlying_price` | The underlying's price the window is centered on. |
| `calls`, `puts` | Ascending strikes: `contract_symbol`, `strike`, `last_price`, `bid`, `ask`, `change_pct`, `volume`, `open_interest`, `implied_volatility`, `in_the_money`, `last_trade_date`. |

`implied_volatility` is a fraction (0.25 is 25% a year).

## Example

```json
{ "symbol": "AAPL", "strikes_each_side": 2 }
```

```json
{
  "as_of": "2026-11-24T15:30:12Z",
  "symbol": "AAPL",
  "expiry": "2026-11-28",
  "expirations": ["2026-11-28", "2026-12-05", "2026-12-19"],
  "underlying_price": 271.49,
  "calls": [
    { "contract_symbol": "AAPL261128C00270000", "strike": 270.0, "last_price": 4.1, "bid": 4.0, "ask": 4.2, "volume": 15230.0, "open_interest": 22100.0, "implied_volatility": 0.24, "in_the_money": true }
  ],
  "puts": []
}
```

## Limits and cost

- Two Yahoo requests (expirations and chain); cached for 1 minute (category `options`).
- A symbol without listed options (crypto, many non-US stocks) returns `not_found`; an
  expiry not in the list returns `invalid_argument` with the valid dates.
