---
title: get_events - earnings, IPO, economic and split calendars
description: The get_events tool lists upcoming earnings, IPOs, economic releases and stock splits, or a symbol's next earnings date, estimates and past surprises.
---

# get_events

Events that move prices. Without symbols it lists the market-wide calendar for a date
range; with symbols it returns each one's earnings calendar.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `kind` | `earnings`, `ipo`, `economic` or `splits` | `earnings` | Which calendar. |
| `start` | date `YYYY-MM-DD` | today | First day. |
| `end` | date `YYYY-MM-DD` | `start` + 7 days | Last day. A range covers at most 92 days. |
| `symbols` | list of up to 10 strings | none | Per-symbol earnings calendars instead of the market-wide list (only with `kind: earnings`). |
| `limit` | integer, 1-50 | `50` | Maximum calendar rows. |
| `response_format` | `concise` or `detailed` | `concise` | Size budget: 20,000 or 80,000 characters. |

## Returns

| Field | Description |
|---|---|
| `kind`, `start`, `end` | The calendar and range served. |
| `events` | Market-wide rows. Earnings: `symbol`, `company`, `marketcap`, `event_name`, `event_start_date`, `timing`, `eps_estimate`, `reported_eps`, `surprise_pct`. IPOs, economic releases and splits have their own columns. |
| `symbols` | Per symbol: `calendar` (next `earnings_date`, `earnings_average`/`high`/`low`, `revenue_average`/`high`/`low`, `dividend_date`, `ex_dividend_date`) and `earnings_dates` (recent and upcoming: `earnings_date`, `eps_estimate`, `reported_eps`, `surprise_pct`). |
| `errors` | Symbols without a calendar. |

## Example

```json
{ "symbols": ["AAPL"] }
```

```json
{
  "as_of": "2026-11-24T15:30:12Z",
  "kind": "earnings",
  "start": "2026-11-24",
  "end": "2026-12-01",
  "symbols": [
    {
      "symbol": "AAPL",
      "calendar": { "earnings_date": ["2027-01-28"], "earnings_average": 2.91, "ex_dividend_date": "2026-11-12" },
      "earnings_dates": [
        { "earnings_date": "2026-10-30T20:00:00Z", "eps_estimate": 2.9, "reported_eps": 3.1, "surprise_pct": 6.9 }
      ]
    }
  ]
}
```

## Limits and cost

- One Yahoo request for a calendar, or two per symbol; cached for 1 hour (category `events`).
- The earnings calendar lists the most active companies.
