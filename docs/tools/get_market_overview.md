---
title: get_market_overview - market open or closed, headline indices
description: The get_market_overview tool says whether a region's market is open and returns its headline indices, futures or rates with change and data delay.
---

# get_market_overview

Whether a region's main market is open, and how its headline indices, futures, rates or
currencies are moving.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `region` | `US`, `GB`, `ASIA`, `EUROPE`, `RATES`, `COMMODITIES`, `CURRENCIES`, `CRYPTOCURRENCIES` | `US` | Market region. |
| `response_format` | `concise` or `detailed` | `concise` | Size budget: 20,000 or 80,000 characters. |

## Returns

| Field | Description |
|---|---|
| `region` | The region asked for. |
| `status` | `name`, `state` (`open` or `closed`), `message` (e.g. "U.S. markets open in 51 minutes"), `opens_at`, `closes_at` (UTC), `timezone`. |
| `indices` | `symbol`, `name`, `type`, `exchange`, `price`, `change`, `change_pct`, `previous_close`, `market_state`, `quote_source`, `delay_min`, `market_time`. |

Futures and many indices are delayed; `warnings` says how many and by how much.

## Example

```json
{ "region": "US" }
```

```json
{
  "as_of": "2026-11-24T13:39:00Z",
  "region": "US",
  "status": { "name": "U.S. markets", "state": "closed", "message": "U.S. markets open in 51 minutes", "opens_at": "2026-11-24T14:30:00Z", "closes_at": "2026-11-24T21:00:00Z", "timezone": "America/New_York" },
  "indices": [
    { "symbol": "ES=F", "name": "S&P Futures", "type": "Futures", "price": 6012.25, "change_pct": 0.31, "market_state": "REGULAR", "delay_min": 10 }
  ],
  "warnings": ["5 of 5 prices are delayed by up to 10 min."]
}
```

## Limits and cost

- Two Yahoo requests (summary and status); cached for 30 seconds (category `market`).
