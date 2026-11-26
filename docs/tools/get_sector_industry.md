---
title: get_sector_industry - sector and industry leaders, ETFs and funds
description: The get_sector_industry tool returns a sector's or industry's overview, top companies, top ETFs and funds, industries, top performers and growth leaders.
---

# get_sector_industry

Who leads a sector or an industry: overview figures, top companies, top ETFs and mutual
funds. Sectors also list their industries; industries add top performers and top growth
companies.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `kind` | `sector` or `industry` | required | What `key` names. |
| `key` | string | required | Sector key, or an industry key such as `semiconductors`. |
| `response_format` | `concise` or `detailed` | `concise` | Size budget: 20,000 or 80,000 characters. |

**Sector keys:** `basic-materials`, `communication-services`, `consumer-cyclical`,
`consumer-defensive`, `energy`, `financial-services`, `healthcare`, `industrials`,
`real-estate`, `technology`, `utilities`. A sector's `industries` list gives the industry
keys.

## Returns

| Field | Description |
|---|---|
| `kind`, `key`, `name` | What was fetched. |
| `sector_key`, `sector_name` | For an industry, its parent sector. |
| `overview` | Company and industry counts, market cap, market weight, employees, description (500 characters). |
| `top_companies` | `symbol`, `name`, `rating`, `market_weight`. |
| `top_etfs`, `top_mutual_funds` | `symbol`, `name` (sectors). |
| `industries` | `key`, `name`, `symbol`, `market_weight` (sectors). |
| `top_performing_companies` | `symbol`, `name`, `ytd_return`, `last_price`, `target_price` (industries). |
| `top_growth_companies` | `symbol`, `name`, `ytd_return`, `growth_estimate` (industries). |

Each list holds at most 25 rows.

## Example

```json
{ "kind": "industry", "key": "semiconductors" }
```

```json
{
  "as_of": "2026-11-24T15:30:12Z",
  "kind": "industry",
  "key": "semiconductors",
  "name": "Semiconductors",
  "sector_key": "technology",
  "top_performing_companies": [
    { "symbol": "NVDA", "name": "NVIDIA Corporation", "ytd_return": 0.35, "last_price": 165.05, "target_price": 210.0 }
  ]
}
```

## Limits and cost

- One Yahoo request; cached for 6 hours (category `sector`).
- An unknown key returns `not_found` listing the valid sector keys.
