"""docs/configuration.md documents every setting the server reads."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from yfinance_agent_mcp.cache import DEFAULT_TTLS
from yfinance_agent_mcp.config import Settings

CONFIGURATION = Path(__file__).parents[2] / "docs" / "configuration.md"

# Settings field -> environment variable(s) that set it.
VARIABLES = {
    "cache_dir": ["YFINANCE_AGENT_MCP_CACHE_DIR"],
    "rate_limit_per_second": ["YFINANCE_AGENT_MCP_RATE_LIMIT"],
    "rate_limit_burst": ["YFINANCE_AGENT_MCP_RATE_BURST"],
    "ttl_overrides": [f"YFINANCE_AGENT_MCP_TTL_{category.upper()}" for category in DEFAULT_TTLS],
    "log_level": ["YFINANCE_AGENT_MCP_LOG_LEVEL"],
    "lang": ["YFINANCE_AGENT_MCP_LANG"],
    "region": ["YFINANCE_AGENT_MCP_REGION"],
    "proxy": ["YFINANCE_AGENT_MCP_PROXY"],
}


def test_every_setting_has_a_known_variable() -> None:
    assert {field.name for field in fields(Settings)} == set(VARIABLES)


def test_every_variable_is_documented() -> None:
    text = CONFIGURATION.read_text(encoding="utf-8")

    missing = [name for names in VARIABLES.values() for name in names if f"`{name}`" not in text]

    assert missing == []
