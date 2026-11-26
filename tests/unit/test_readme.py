"""README.md is the GitHub page and the PyPI description, and the MCP Registry reads it."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
README = (ROOT / "README.md").read_text(encoding="utf-8")
TOOLS = [
    "search_symbols",
    "get_quotes",
    "get_market_overview",
    "get_price_history",
    "get_news",
    "screen_securities",
    "get_sector_industry",
    "get_events",
    "get_fundamentals",
    "get_analyst_view",
    "get_options",
    "get_ticker_dataset",
    "get_live_quotes",
]


def test_registry_ownership_marker_matches_server_json() -> None:
    name = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))["name"]

    assert f"<!-- mcp-name: {name} -->" in README


def test_every_link_and_image_is_absolute_because_pypi_renders_the_readme() -> None:
    targets = re.findall(r"\]\(([^)\s]+)", README) + re.findall(r'src="([^"]+)"', README)

    assert targets
    assert [target for target in targets if not target.startswith("https://")] == []


def test_all_thirteen_tools_are_listed() -> None:
    assert [tool for tool in TOOLS if f"`{tool}`" not in README] == []
