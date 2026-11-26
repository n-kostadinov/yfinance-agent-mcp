---
title: get_ticker_dataset - holders, insider trades, dividends, filings
description: The get_ticker_dataset tool returns any other yfinance data for a symbol - holders, insider trades, dividends, splits, SEC filings, ESG, fund holdings.
---

# get_ticker_dataset

Everything else yfinance knows about a symbol, from an allowlist of datasets. Tables come
back as paged rows; text, dictionary and list datasets come back as `data`.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | string | required | One Yahoo symbol. |
| `dataset` | a dataset name (below) | required | Which dataset. |
| `limit` | integer, 1-25 | `25` | Rows per page. |
| `offset` | integer, 0 or more | `0` | First row; use `next_offset` from the previous answer. |
| `columns` | list of strings | all | Keep only these columns; a first answer lists them in `columns`. |
| `response_format` | `concise` or `detailed` | `concise` | Size budget: 20,000 or 80,000 characters. |

## Datasets

| Dataset | Contents |
|---|---|
| `info` | Yahoo's raw quote summary for the symbol (about 180 fields). |
| `major_holders` | Insider and institutional ownership percentages. |
| `institutional_holders`, `mutualfund_holders` | Top holders with shares, value and change. |
| `insider_purchases` | Insider buying and selling over 6 months. |
| `insider_transactions` | Individual insider trades. |
| `insider_roster_holders` | Insiders and their holdings. |
| `dividends`, `splits`, `capital_gains`, `actions` | Corporate actions, newest first. |
| `isin` | The ISIN code. |
| `sustainability` | ESG scores, where Yahoo has them. |
| `sec_filings` | Recent SEC filings with type, title and links. |
| `earnings_history` | Reported versus estimated EPS for recent quarters. |
| `history_metadata` | Exchange, timezone, trading periods and valid ranges from the chart. |
| `fund_description`, `fund_overview`, `fund_operations` | For ETFs and funds: description, category and family, fees and turnover. |
| `fund_asset_classes`, `fund_sector_weightings`, `fund_bond_ratings` | For ETFs and funds: allocations. |
| `fund_top_holdings`, `fund_equity_holdings`, `fund_bond_holdings` | For ETFs and funds: holdings and their averages. |

Fund datasets exist only for ETFs and mutual funds; for a stock they return `not_found`.

## Returns

| Field | Description |
|---|---|
| `symbol`, `dataset` | The request as served. |
| `columns` | All columns of a table dataset. |
| `total_rows` | Rows in the whole dataset. |
| `rows` | The page of rows, with snake_case keys; time-indexed tables are newest first. |
| `data` | The value of a non-table dataset (text, dictionary or list). |
| `truncated`, `next_offset` | Whether more rows exist, and the `offset` to request them. |

## Example

```json
{ "symbol": "AAPL", "dataset": "dividends", "limit": 2 }
```

```json
{
  "as_of": "2026-11-24T15:30:12Z",
  "symbol": "AAPL",
  "dataset": "dividends",
  "columns": ["dividends"],
  "total_rows": 93,
  "rows": [
    { "date": "2026-11-10T05:00:00Z", "dividends": 0.26 },
    { "date": "2026-08-11T04:00:00Z", "dividends": 0.26 }
  ],
  "truncated": true,
  "next_offset": 2
}
```

## Limits and cost

- One to three Yahoo requests; cached for 6 hours (category `datasets`).
