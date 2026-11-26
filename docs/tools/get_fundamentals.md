---
title: get_fundamentals - financial statements, valuation and key ratios
description: The get_fundamentals tool returns income statement, balance sheet, cash flow, valuation history or key ratios for one symbol, one record per period.
---

# get_fundamentals

Financial statements, valuation history or key ratios for one symbol.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | string | required | One Yahoo symbol. |
| `statement` | `income`, `balance`, `cashflow`, `valuation` or `key_stats` | `income` | What to fetch. |
| `freq` | `yearly`, `quarterly` or `trailing` | `quarterly` | Statement periods; `trailing` is the last twelve months and exists for `income` and `cashflow` only. Ignored for `valuation` and `key_stats`. |
| `response_format` | `concise` or `detailed` | `concise` | `concise` keeps the key line items; `detailed` returns every line. |

## Returns

| Field | Description |
|---|---|
| `symbol`, `statement`, `freq` | The request as served. |
| `periods` | One record per period, newest first: `period` plus line items as snake_case keys. |
| `key_stats` | For `key_stats`: valuation, margins, growth, balance sheet and ownership ratios. |

Key line items in `concise` mode:

- **income:** `total_revenue`, `gross_profit`, `operating_income`, `net_income`,
  `diluted_eps`, `ebitda`, `research_and_development`, `operating_expense`.
- **balance:** `total_assets`, `total_liabilities_net_minority_interest`,
  `stockholders_equity`, `cash_and_cash_equivalents`, `total_debt`, `net_debt`,
  `working_capital`.
- **cashflow:** `operating_cash_flow`, `capital_expenditure`, `free_cash_flow`,
  `repurchase_of_capital_stock`, `cash_dividends_paid`.
- **valuation:** every measure (`market_cap`, `enterprise_value`, `trailing_p_e`,
  `forward_p_e`, `peg_ratio_5yr_expected`, `price_sales`, `price_book`,
  `enterprise_value_revenue`, `enterprise_value_ebitda`), with `period` `Current` first.

`key_stats` fields: `market_cap`, `enterprise_value`, `trailing_pe`, `forward_pe`,
`peg_ratio`, `price_to_book`, `price_to_sales`, `ev_to_revenue`, `ev_to_ebitda`,
`profit_margin`, `gross_margin`, `operating_margin`, `return_on_equity`, `return_on_assets`,
`revenue_growth`, `earnings_growth`, `debt_to_equity`, `current_ratio`, `quick_ratio`,
`total_cash`, `total_debt`, `free_cash_flow`, `dividend_yield_pct`, `payout_ratio`, `beta`,
`shares_outstanding`, `float_shares`, `short_percent_of_float`, `held_by_insiders`,
`held_by_institutions`. Margins, growth and ownership are fractions (0.25 is 25%).

## Example

```json
{ "symbol": "MSFT", "statement": "cashflow", "freq": "yearly" }
```

```json
{
  "as_of": "2026-11-24T15:30:12Z",
  "symbol": "MSFT",
  "statement": "cashflow",
  "freq": "yearly",
  "periods": [
    { "period": "2026-06-30", "operating_cash_flow": 136000000000.0, "capital_expenditure": -64000000000.0, "free_cash_flow": 72000000000.0 }
  ]
}
```

## Limits and cost

- One Yahoo request per statement; `key_stats` needs about three. Cached for 6 hours
  (category `fundamentals`).
