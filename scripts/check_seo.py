"""Check the built documentation site for the SEO basics every page must have.

    uv run python scripts/check_seo.py site

Every page needs one unique <title>, a meta description of 50-160 characters, an Open Graph
image and a canonical URL listed in sitemap.xml. The home page needs SoftwareApplication
JSON-LD, and the site needs llms.txt and a 404 page.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

MIN_DESCRIPTION, MAX_DESCRIPTION = 50, 160
_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


@dataclass
class PageHead:
    """The SEO-relevant parts of a page's <head>."""

    titles: list[str] = field(default_factory=list)
    description: str | None = None
    canonical: str | None = None
    og_image: str | None = None
    json_ld: list[str] = field(default_factory=list)


class _HeadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.head = PageHead()
        self._capture: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "title" or (tag == "script" and values.get("type") == "application/ld+json"):
            self._capture, self._text = tag, []
        elif tag == "meta" and values.get("name") == "description":
            self.head.description = values.get("content", "")
        elif tag == "meta" and values.get("property") == "og:image":
            self.head.og_image = values.get("content")
        elif tag == "link" and values.get("rel") == "canonical":
            self.head.canonical = values.get("href")

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != self._capture:
            return
        text = "".join(self._text).strip()
        (self.head.titles if tag == "title" else self.head.json_ld).append(text)
        self._capture = None


def parse_head(html: str) -> PageHead:
    parser = _HeadParser()
    parser.feed(html)
    return parser.head


def check_site(site: Path) -> list[str]:
    """Return every SEO problem found in the built site; empty means it passes."""
    problems = _site_problems(site)
    in_sitemap = _sitemap_urls(site)
    first_use: dict[str, str] = {}
    for path in sorted(site.rglob("index.html")):
        relative = path.relative_to(site).as_posix()
        if relative.startswith("assets/"):
            continue
        head = parse_head(path.read_text(encoding="utf-8"))
        problems += _page_problems(relative, head, in_sitemap, first_use)
    return problems


def _site_problems(site: Path) -> list[str]:
    problems = []
    if not (site / "404.html").is_file():
        problems.append("404.html is missing")
    llms = site / "llms.txt"
    if not llms.is_file() or not llms.read_text(encoding="utf-8").strip():
        problems.append("llms.txt is missing or empty")
    if not (site / "sitemap.xml").is_file():
        problems.append("sitemap.xml is missing")
    return problems


def _sitemap_urls(site: Path) -> set[str]:
    sitemap = site / "sitemap.xml"
    if not sitemap.is_file():
        return set()
    root = ElementTree.fromstring(sitemap.read_text(encoding="utf-8"))
    return {(loc.text or "").strip() for loc in root.iter(f"{_SITEMAP_NS}loc")}


def _page_problems(
    relative: str, head: PageHead, in_sitemap: set[str], first_use: dict[str, str]
) -> list[str]:
    problems = []
    if len(head.titles) != 1:
        problems.append(f"{relative}: expected one <title>, found {len(head.titles)}")
    elif head.titles[0] in first_use:
        problems.append(
            f"{relative}: title {head.titles[0]!r} also used by {first_use[head.titles[0]]}"
        )
    else:
        first_use[head.titles[0]] = relative
    if head.description is None:
        problems.append(f"{relative}: no meta description")
    elif not MIN_DESCRIPTION <= len(head.description) <= MAX_DESCRIPTION:
        problems.append(
            f"{relative}: description is {len(head.description)} characters, "
            f"needs {MIN_DESCRIPTION}-{MAX_DESCRIPTION}"
        )
    if not head.og_image:
        problems.append(f"{relative}: no og:image")
    if not head.canonical:
        problems.append(f"{relative}: no canonical URL")
    elif head.canonical not in in_sitemap:
        problems.append(f"{relative}: canonical URL is not in sitemap.xml")
    if relative == "index.html" and not _has_software_json_ld(head.json_ld):
        problems.append("index.html: no SoftwareApplication JSON-LD")
    return problems


def _has_software_json_ld(blocks: list[str]) -> bool:
    for block in blocks:
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "SoftwareApplication":
            return True
    return False


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a built docs site for SEO basics.")
    parser.add_argument("site", type=Path, help="the built site folder, e.g. site")
    args = parser.parse_args(argv)
    problems = check_site(args.site)
    for problem in problems:
        print(problem)
    pages = sum(1 for p in args.site.rglob("index.html") if "assets" not in p.parts)
    print(f"{len(problems)} problem(s) in {pages} page(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
