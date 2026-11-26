from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from yfinance_agent_mcp.__main__ import main

PYPROJECT = Path(__file__).parents[2] / "pyproject.toml"


def test_version_flag_prints_the_project_version(capsys: pytest.CaptureFixture[str]) -> None:
    expected = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]

    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"yfinance-agent-mcp {expected}"


def test_invalid_environment_exits_with_usage_error_before_serving(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("YFINANCE_AGENT_MCP_RATE_LIMIT", "fast")

    exit_code = main([])

    assert exit_code == 2
    assert "YFINANCE_AGENT_MCP_RATE_LIMIT" in capsys.readouterr().err


def test_unknown_cache_category_exits_with_usage_error_before_serving(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setenv("YFINANCE_AGENT_MCP_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("YFINANCE_AGENT_MCP_TTL_QUOTE", "5")

    exit_code = main([])

    assert exit_code == 2
    assert "unknown cache categories ['quote']" in capsys.readouterr().err
