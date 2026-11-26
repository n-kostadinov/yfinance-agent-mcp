---
title: SEO checklist - getting yfinance-agent-mcp found
description: Manual steps that make yfinance-agent-mcp easy to find - Search Console, GitHub metadata and social preview, and MCP directory listings.
---

# SEO checklist

The build handles on-page SEO automatically (see [writing the docs](docs.md)). These steps
need the maintainer's accounts and are done by hand.

## Search engines

- [ ] **Google Search Console:** add the property
      `https://n-kostadinov.github.io/yfinance-agent-mcp/` (URL prefix), verify it with the
      HTML tag method through a template override, and submit `sitemap.xml`.
- [ ] **Bing Webmaster Tools:** import the site from Search Console.
- [ ] Check after a week that pages are indexed, and which queries bring visitors.

A project site lives under `/yfinance-agent-mcp/`, so a `robots.txt` there would be ignored
by crawlers; submitting the sitemap is what counts.

## GitHub

- [ ] Description, homepage and topics set (`gh repo edit`, see [releasing](releasing.md)).
- [ ] Social preview image uploaded (Settings → General).
- [ ] The README's first lines say what the project is, with the keywords "yfinance",
      "Yahoo Finance", "MCP server" and "AI agents".
- [ ] Each GitHub Release has notes; releases appear in search results and feeds.

## PyPI

Set automatically from `pyproject.toml`: summary, keywords, classifiers, project links and
the README. Check the [project page](https://pypi.org/project/yfinance-agent-mcp/) after
each release.

## MCP directories

- [ ] **Official MCP Registry:** published by the release workflow.
- [ ] [awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers): open a pull
      request adding the server under Finance.
- [ ] [Glama](https://glama.ai/mcp/servers), [Smithery](https://smithery.ai/),
      [PulseMCP](https://www.pulsemcp.com/) and [mcp.so](https://mcp.so/): submit the
      repository.
- [ ] Mention the Claude Code plugin marketplace: `n-kostadinov/yfinance-agent-mcp`.

## Content

- [ ] Keep each tool page's examples current; they rank for specific queries.
- [ ] Add a guide when a common question comes up in issues.
