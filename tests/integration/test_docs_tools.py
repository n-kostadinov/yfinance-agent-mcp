"""Each tool has a reference page that documents every parameter of its live schema."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fakes import FakeGateway
from yfinance_agent_mcp.config import Settings
from yfinance_agent_mcp.server import create_server

TOOL_PAGES = Path(__file__).parents[2] / "docs" / "tools"


@pytest.mark.anyio
async def test_every_tool_has_a_page_that_documents_each_parameter(tmp_path: Path) -> None:
    server = create_server(Settings(cache_dir=tmp_path), gateway=FakeGateway())

    undocumented: dict[str, list[str]] = {}
    for tool in await server.list_tools():
        page = TOOL_PAGES / f"{tool.name}.md"
        text = page.read_text(encoding="utf-8") if page.is_file() else ""
        parameters = tool.input_schema.get("properties", {})
        missing = [name for name in parameters if f"| `{name}` |" not in text]
        if not text or missing:
            undocumented[tool.name] = missing or ["<no page>"]

    assert undocumented == {}
