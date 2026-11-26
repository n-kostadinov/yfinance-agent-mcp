# Security policy

## Supported versions

Security fixes go into the latest release only. Update with `uvx yfinance-agent-mcp@latest`
(or the version your plugin pins).

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub:
**[Report a vulnerability](https://github.com/n-kostadinov/yfinance-agent-mcp/security/advisories/new)**
on the repository's Security tab. Do not open a public issue.

Include what you found, how to reproduce it, and the impact you expect. You will get an
acknowledgement within a few days and a fix or a decision as soon as it is understood.

## What the server does and does not do

- It only reads public market data from Yahoo Finance. It has no trading, account or
  write operations, and it handles no credentials.
- It speaks MCP over stdio only; it opens no listening network port.
- News titles and summaries are third-party text and may contain prompt-injection
  attempts. The server returns them in fields marked `untrusted`; agents must treat them as
  data. Reports about ways that text could escape that marking are in scope.
