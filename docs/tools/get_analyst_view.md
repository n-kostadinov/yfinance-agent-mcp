---
title: get_analyst_view - price targets, ratings and estimate revisions
description: The get_analyst_view tool returns analyst price targets, buy-hold-sell counts, recent upgrades and downgrades, EPS and revenue estimates and revisions.
---

# get_analyst_view

What analysts expect for one symbol.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | string | required | One Yahoo symbol. |
| `rating_changes` | integer, 1-50 | `10` | How many recent upgrades and downgrades to show. |
| `response_format` | `concise` or `detailed` | `concise` | Size budget: 20,000 or 80,000 characters. |

## Returns

| Field | Description |
|---|---|
| `price_targets` | `current` price and the analysts' `high`, `low`, `mean` and `median` targets. |
| `recommendations` | Counts of `strong_buy`, `buy`, `hold`, `sell`, `strong_sell` per `period` (`0m` this month, `-1m` last month...). |
| `rating_changes` | Newest first: `grade_date`, `firm`, `to_grade`, `from_grade`, `action`, `price_target_action`, `current_price_target`, `prior_price_target`. |
| `earnings_estimate` | Per `period` (`0q` this quarter, `+1q` next quarter, `0y` this year, `+1y` next year): `avg`, `low`, `high`, `year_ago_eps`, `number_of_analysts`, `growth`. |
| `revenue_estimate` | Same periods: `avg`, `low`, `high`, `number_of_analysts`, `year_ago_revenue`, `growth`. |
| `eps_trend` | How the EPS estimate moved: `current`, `7days_ago`, `30days_ago`, `60days_ago`, `90days_ago`. |
| `eps_revisions` | Number of `up_last7days`, `up_last30days`, `down_last7_days`, `down_last30days` revisions. |
| `growth_estimates` | `stock_trend` versus `index_trend` per period, including long-term growth (`LTG`). |

Lists Yahoo has no data for come back empty.

## Example

```json
{ "symbol": "AAPL", "rating_changes": 3 }
```

```json
{
  "as_of": "2026-11-24T15:30:12Z",
  "symbol": "AAPL",
  "price_targets": { "current": 271.49, "high": 350.0, "low": 200.0, "mean": 300.2, "median": 305.0 },
  "recommendations": [{ "period": "0m", "strong_buy": 7, "buy": 20, "hold": 12, "sell": 1, "strong_sell": 1 }],
  "rating_changes": [
    { "grade_date": "2026-11-20T00:00:00Z", "firm": "Example Securities", "to_grade": "Buy", "from_grade": "Hold", "action": "up", "current_price_target": 310.0 }
  ]
}
```

## Limits and cost

- About six Yahoo requests; cached for 1 hour (category `analysts`).
