---
title: Writing the docs - Zensical site, SEO rules and checks
description: How the yfinance-agent-mcp documentation is built with Zensical - page front matter, titles and descriptions, tool pages, llms.txt and the SEO checks.
---

# Writing the docs

The site is built with [Zensical](https://zensical.org/) from `docs/`, configured in
`zensical.toml`, and published to GitHub Pages by `.github/workflows/docs.yml`.

## Preview and build

```bash
uv run zensical serve              # http://localhost:8000, reloads on save
uv run zensical build --clean      # writes site/
uv run python scripts/check_seo.py site
```

## Every page

Start every page with front matter:

```markdown
---
title: What the page is about, in words people search for
description: One or two sentences, 50 to 160 characters, that make someone click.
---
```

- The `title` becomes the browser and search result title; it must be unique.
- The `description` becomes the meta description and the social card text.
- Add the page to `nav` in `zensical.toml`, and to an `llms.txt` section if it is new.
- Link with relative paths to `.md` files; the build warns about broken links.

## Tool pages

Each tool has `docs/tools/<tool>.md` with a parameter table. The row for each parameter
starts with the parameter in backticks, for example `` | `symbols` | ``. A test compares
the tables with the live tool schemas and fails when a parameter is missing, so update the
page with the code.

## What the build produces

- `sitemap.xml` and canonical links, from `site_url`.
- A social card image and Open Graph and Twitter tags for every page (the `social` plugin).
- Meta descriptions for pages without one (the `meta-descriptions` plugin; set them anyway).
- `llms.txt` and a Markdown copy of each page for AI assistants (the `llmstxt` plugin).
- SoftwareApplication JSON-LD on the home page and a helpful 404 page (`overrides/`).

## Checks

- `scripts/check_seo.py` fails when a page lacks a unique title, a 50-160 character
  description, an Open Graph image, a canonical URL in the sitemap, or when `llms.txt`,
  the 404 page or the home page's JSON-LD is missing.
- Lighthouse CI (`lighthouserc.json`) requires an SEO score of at least 0.95 on the home
  page, the tool overview and the installation page.

Both run in the docs workflow on every pull request and every push to `main`, and the site
is deployed only when they pass.
