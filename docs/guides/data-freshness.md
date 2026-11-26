---
title: Data freshness - delayed quotes, market state and as_of times
description: How current is a Yahoo Finance price? Read as_of, market_time, market_state and delay_min, and know which exchanges are delayed before acting.
---

# Data freshness

A price is only useful if you know how old it is. Yahoo Finance data comes with different
delays per exchange, and the server adds its own short cache. These fields tell an agent
exactly how current an answer is.

## The fields

| Field | Where | Meaning |
|---|---|---|
| `as_of` | every answer | When the server fetched the data from Yahoo. A cached answer keeps its original `as_of`. |
| `market_time` | `get_quotes` | Time of the last regular-session price. |
| `market_state` | `get_quotes`, `get_market_overview` | `PRE`, `REGULAR`, `POST` or `CLOSED` (Yahoo also uses `PREPRE` and `POSTPOST`). |
| `delay_min` | `get_quotes` with `include_details`, `get_market_overview` | Minutes the exchange delays its data. `0` is real time. |
| `quote_source` | same as `delay_min` | Yahoo's source, e.g. `Nasdaq Real Time Price` or `Delayed Quote`. |
| `exchange_time`, `age_seconds` | `get_live_quotes` | When the exchange printed the tick, and how long ago the server received it. |
| `last_bar_time` | `get_price_history` | Start of the most recent bar. |

## What to expect

- **US stocks** often show `Nasdaq Real Time Price`, yet Yahoo may still report
  `delay_min: 15` for the exchange; trust `market_time` for the actual age.
- **European exchanges** (for example `SAP.DE`) are typically delayed by 15 minutes.
- **Futures and indices** in `get_market_overview` are often delayed by 10 to 20 minutes.
- **Crypto** (`BTC-USD`) trades around the clock with no delay.
- **Outside regular hours** `price` is the last regular-session price; pre- and post-market
  prices are in `details` (`pre_market_price`, `post_market_price`) with `include_details`.

## Rules for agents

1. Before acting on a price, read `market_time` and `market_state`; if the market is closed,
   say the price is the last close.
2. If `delay_min` is above 0, say the quote is delayed, and by how much.
3. For decisions that need the current price, use `get_live_quotes`, which reports each
   tick's age.
4. When comparing data from several calls, compare their `as_of` times; cached answers can be
   a few seconds to hours old depending on the [cache category](../configuration.md#cache-expiry).

## Not for live trading

Yahoo Finance data is unofficial, can be delayed, incomplete or wrong, and is meant for
personal use. Verify prices with your broker before any order. See the
[disclaimer](../disclaimer.md).
