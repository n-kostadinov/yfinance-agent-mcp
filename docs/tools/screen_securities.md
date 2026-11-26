---
title: screen_securities - stock, ETF and fund screeners for AI agents
description: The screen_securities tool runs Yahoo's predefined screens such as day gainers or a custom query, returning compact rows with price, volume and market cap.
---

# screen_securities

Find candidates: run one of Yahoo's predefined screens, or your own query over equities,
mutual funds or ETFs.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `preset` | a predefined screen name (below) | none | Use one of Yahoo's screens. |
| `query` | JSON object | none | A custom screen instead of a preset (format below). |
| `security_type` | `equity`, `fund` or `etf` | `equity` | What a custom query screens. |
| `sort_field` | string | none | Yahoo field to sort by, e.g. `percentchange`, `intradaymarketcap`, `dayvolume`. |
| `ascending` | boolean | `false` | Sort order. |
| `count` | integer, 1-25 | `25` | Rows to return. |
| `response_format` | `concise` or `detailed` | `concise` | Size budget: 20,000 or 80,000 characters. |

Give exactly one of `preset` or `query`.

**Presets:** `day_gainers`, `day_losers`, `most_actives`, `most_shorted_stocks`,
`aggressive_small_caps`, `small_cap_gainers`, `growth_technology_stocks`,
`undervalued_growth_stocks`, `undervalued_large_caps`, `top_etfs_us`,
`top_performing_etfs`, `technology_etfs`, `bond_etfs`, `top_mutual_funds`,
`conservative_foreign_funds`, `high_yield_bond`, `portfolio_anchors`,
`solid_large_growth_funds`, `solid_midcap_growth_funds`.

### Custom queries

A query is a tree of `{"operator": ..., "operands": [...]}` nodes. Operators: `and`, `or`,
`eq`, `gt`, `lt`, `gte`, `lte`, `btwn`, `is-in`. Leaf operands are a field name followed by
values:

```json
{
  "operator": "and",
  "operands": [
    { "operator": "gt", "operands": ["percentchange", 3] },
    { "operator": "eq", "operands": ["region", "us"] },
    { "operator": "gte", "operands": ["intradaymarketcap", 2000000000] }
  ]
}
```

Unknown fields or operators are rejected with `invalid_argument`. Valid field names are
those of yfinance's `EquityQuery`, `FundQuery` and `ETFQuery` (for example `region`,
`sector`, `exchange`, `percentchange`, `intradaymarketcap`, `peratio.lasttwelvemonths`).

## Returns

| Field | Description |
|---|---|
| `screen` | The preset name, or `custom`. |
| `title` | Yahoo's title for the screen. |
| `total` | How many securities match in total. |
| `rows` | `symbol`, `name`, `price`, `change_pct`, `volume`, `avg_volume_3m`, `market_cap`, `exchange`. |

## Example

```json
{ "preset": "day_gainers", "count": 5 }
```

```json
{
  "as_of": "2026-11-24T15:30:12Z",
  "screen": "day_gainers",
  "title": "Day Gainers",
  "total": 120,
  "rows": [
    { "symbol": "NVDA", "name": "NVIDIA Corporation", "price": 165.05, "change_pct": 31.48, "volume": 776225888.0, "avg_volume_3m": 180634662.0, "market_cap": 3985462263808.0, "exchange": "NasdaqGS" }
  ]
}
```

## Limits and cost

- One Yahoo request; cached for 1 minute (category `screen`).
