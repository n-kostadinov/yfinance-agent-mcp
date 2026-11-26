"""server.json is what the MCP Registry lists; it must match the registry schema and the package."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import jsonschema

ROOT = Path(__file__).parents[2]
SERVER_JSON = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
SCHEMA = json.loads(
    (ROOT / "tests" / "fixtures" / "server.schema.json").read_text(encoding="utf-8")
)
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def test_server_json_follows_the_registry_schema() -> None:
    jsonschema.validate(SERVER_JSON, SCHEMA)


def test_server_json_declares_the_pypi_package_run_with_uvx_over_stdio() -> None:
    assert SERVER_JSON["$schema"] == SCHEMA["$id"]
    assert SERVER_JSON["name"] == "io.github.n-kostadinov/yfinance-agent-mcp"
    assert SERVER_JSON["packages"] == [
        {
            "registryType": "pypi",
            "identifier": PROJECT["name"],
            "version": PROJECT["version"],
            "runtimeHint": "uvx",
            "transport": {"type": "stdio"},
        }
    ]
