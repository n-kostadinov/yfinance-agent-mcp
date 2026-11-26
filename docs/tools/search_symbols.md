---
title: search_symbols - find Yahoo Finance tickers by name or keyword
description: The search_symbols tool turns a company name, ticker or keyword into Yahoo Finance symbols, optionally limited to equities, ETFs, funds, indices or crypto.
---

# search_symbols

Find Yahoo Finance symbols for a company name, ticker or keyword. Every other tool needs an
exact Yahoo symbol such as `AAPL`, `SAP.DE`, `BTC-USD`, `^GSPC` or `EURUSD=X`; call this
first when you only know a name.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | string, 1-100 characters | required | Company name, ticker or keyword, e.g. `nvidia`, `SAP`, `gold`. |
| `kind` | `any`, `equity`, `etf`, `mutualfund`, `index`, `future`, `currency`, `cryptocurrency` | `any` | Narrow the search to one kind of security. |
| `limit` | integer, 1-10 | `10` | Maximum matches. |
| `response_format` | `concise` or `detailed` | `concise` | Size budget: 20,000 or 80,000 characters. |

`kind: any` uses Yahoo's full-text search, which also returns sector and industry; a
specific kind uses Yahoo's lookup, which covers more exchanges.

## Returns

| Field | Description |
|---|---|
| `query`, `kind` | The request as given. |
| `matches` | Best matches first: `symbol`, `name`, `type` (`EQUITY`, `ETF`, `CRYPTOCURRENCY`...), `exchange`, `sector`, `industry`. |

No matches is not an error: `matches` is empty and `warnings` suggests what to try.

## Example

```json
{ "query": "nvidia", "kind": "equity", "limit": 3 }
```

```json
{
  "as_of": "2026-11-24T15:30:12Z",
  "query": "nvidia",
  "kind": "equity",
  "matches": [
    { "symbol": "NVDA", "name": "NVIDIA Corporation", "type": "EQUITY", "exchange": "NMS", "sector": "Technology", "industry": null },
    { "symbol": "NVD.DE", "name": "NVIDIA CORP.", "type": "EQUITY", "exchange": "GER", "sector": "Technology", "industry": null }
  ]
}
```

## Limits and cost

- One Yahoo request; answers are cached for 2 minutes (cache category `search`).
- See also [`get_quotes`](get_quotes.md) to price the symbols you found.
