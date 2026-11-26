"""The repo is a Claude Code marketplace whose plugin runs the published server and a skill."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.fakes import FakeGateway
from yfinance_agent_mcp.config import Settings
from yfinance_agent_mcp.server import create_server

ROOT = Path(__file__).parents[2]
PLUGIN = ROOT / "plugins" / "yfinance"
SKILL = PLUGIN / "skills" / "market-research" / "SKILL.md"


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_marketplace_lists_the_yfinance_plugin_from_its_folder() -> None:
    marketplace = read_json(ROOT / ".claude-plugin" / "marketplace.json")

    assert marketplace["name"] == "yfinance-agent-mcp"
    assert marketplace["plugins"] == [
        {
            "name": "yfinance",
            "source": "./plugins/yfinance",
            "description": read_json(PLUGIN / ".claude-plugin" / "plugin.json")["description"],
            "version": read_json(PLUGIN / ".claude-plugin" / "plugin.json")["version"],
        }
    ]


def test_plugin_starts_the_published_server_with_uvx_at_a_pinned_version() -> None:
    servers = read_json(PLUGIN / ".mcp.json")["mcpServers"]

    assert isinstance(servers, dict)
    assert servers["yfinance"]["command"] == "uvx"
    (package,) = servers["yfinance"]["args"]
    assert re.fullmatch(r"yfinance-agent-mcp@\d+\.\d+\.\d+", package)


def test_skill_describes_when_to_use_it() -> None:
    text = SKILL.read_text(encoding="utf-8")

    frontmatter = text.split("---")[1]
    assert re.search(r"^description: .{40,}", frontmatter, re.MULTILINE)


@pytest.mark.anyio
async def test_every_tool_the_skill_names_exists_on_the_server(tmp_path: Path) -> None:
    server = create_server(Settings(cache_dir=tmp_path), gateway=FakeGateway())
    tools = {tool.name for tool in await server.list_tools()}

    named = set(re.findall(r"`((?:get|search|screen)_[a-z_]+)`", SKILL.read_text(encoding="utf-8")))

    assert named
    assert named <= tools, named - tools
