from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parents[2]
VERSIONED_FILES = [
    "pyproject.toml",
    "server.json",
    ".claude-plugin/marketplace.json",
    "plugins/yfinance/.claude-plugin/plugin.json",
    "plugins/yfinance/.mcp.json",
]


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "set_version", ROOT / "scripts" / "set_version.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


set_version = load_script()


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    for name in VERSIONED_FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / name, target)
    return tmp_path


def set_pyproject_version(root: Path, version: str) -> None:
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    pyproject.write_text(
        re.sub(r'(?m)^version = ".*"$', f'version = "{version}"', text, count=1), encoding="utf-8"
    )


def read(root: Path, name: str) -> Any:
    return json.loads((root / name).read_text(encoding="utf-8"))


def test_repository_files_all_carry_the_pyproject_version() -> None:
    assert set_version.mismatches(ROOT) == []


def test_write_version_updates_every_versioned_field(repo_copy: Path) -> None:
    set_pyproject_version(repo_copy, "1.2.3")

    set_version.write_version(repo_copy, "1.2.3")

    assert set_version.mismatches(repo_copy) == []
    assert read(repo_copy, "server.json")["packages"][0]["version"] == "1.2.3"
    assert read(repo_copy, "plugins/yfinance/.mcp.json")["mcpServers"]["yfinance"]["args"] == [
        "yfinance-agent-mcp@1.2.3"
    ]


def test_each_file_that_disagrees_is_reported(repo_copy: Path) -> None:
    plugin = repo_copy / "plugins/yfinance/.claude-plugin/plugin.json"
    data = json.loads(plugin.read_text(encoding="utf-8"))
    plugin.write_text(json.dumps({**data, "version": "9.9.9"}), encoding="utf-8")

    problems = set_version.mismatches(repo_copy)

    assert problems == [
        "plugins/yfinance/.claude-plugin/plugin.json version is 9.9.9, pyproject.toml has "
        + set_version.read_version(repo_copy)
    ]


def test_release_tag_must_match_the_version(repo_copy: Path) -> None:
    version = set_version.read_version(repo_copy)

    assert set_version.mismatches(repo_copy, tag=f"v{version}") == []
    assert set_version.mismatches(repo_copy, tag="v99.0.0") == [
        f"tag v99.0.0 does not match pyproject.toml version {version}"
    ]


def test_bump_runs_uv_and_syncs_the_files(repo_copy: Path) -> None:
    commands: list[list[str]] = []

    def fake_uv(command: list[str], **_kwargs: object) -> None:
        commands.append(command)
        set_pyproject_version(repo_copy, "0.2.0")

    new_version = set_version.bump(repo_copy, "minor", run=fake_uv)

    assert new_version == "0.2.0"
    assert commands == [["uv", "version", "--bump", "minor", "--frozen"]]
    assert set_version.mismatches(repo_copy) == []


def test_check_command_exits_with_1_and_names_the_problem(
    repo_copy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    set_pyproject_version(repo_copy, "3.0.0")

    exit_code = set_version.main(["--check"], root=repo_copy)

    assert exit_code == 1
    assert "server.json version is" in capsys.readouterr().err
