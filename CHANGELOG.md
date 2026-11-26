# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-24

### Added

- Read-only MCP server over stdio, started with `uvx yfinance-agent-mcp`.
- 13 tools: `search_symbols`, `get_quotes`, `get_market_overview`, `get_price_history`,
  `get_news`, `screen_securities`, `get_sector_industry`, `get_events`, `get_fundamentals`,
  `get_analyst_view`, `get_options`, `get_ticker_dataset` and `get_live_quotes`.
- Price history summaries with returns, SMA 20/50/200, RSI 14, ATR 14, the 52-week range
  and volume versus average.
- Freshness fields on every answer (`as_of`; `market_state`, `quote_source` and
  `delay_min` for prices) and actionable error codes (`rate_limited`, `not_found`,
  `invalid_argument`, `upstream_error`).
- A process-wide rate limit with a pause after HTTP 429, a result cache with per-category
  expiry times, and response size budgets (20,000 characters by default, 80,000 detailed).
- News text returned in fields marked `untrusted`.
- Claude Code plugin marketplace with the `yfinance` plugin and a market-research skill.
- Documentation site, MCP Registry metadata and GitHub Actions for CI, docs, live tests
  and releases.

[Unreleased]: https://github.com/n-kostadinov/yfinance-agent-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/n-kostadinov/yfinance-agent-mcp/releases/tag/v0.1.0
