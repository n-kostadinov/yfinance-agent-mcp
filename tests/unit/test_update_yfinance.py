from __future__ import annotations

import importlib.util
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parents[2]
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
REPO_FILES = [
    "pyproject.toml",
    "CHANGELOG.md",
    "server.json",
    ".claude-plugin/marketplace.json",
    "plugins/yfinance/.claude-plugin/plugin.json",
    "plugins/yfinance/.mcp.json",
]


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "update_yfinance", ROOT / "scripts" / "update_yfinance.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses look the module up, and the script imports its sibling scripts the way
    # Python finds them when it runs scripts/update_yfinance.py.
    sys.modules[spec.name] = module
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(ROOT / "scripts"))
    return module


update_yfinance = load_script()


def upload(when: str, yanked: bool = False) -> dict[str, Any]:
    return {"upload_time_iso_8601": when, "yanked": yanked}


OLD = [upload("2026-08-01T10:00:00.000000Z")]


def choose(releases: dict[str, list[dict[str, Any]]], floor: str = "1.8.0", cap: str = "2"):
    return update_yfinance.choose(releases, floor, cap, NOW)


def test_choose_picks_the_newest_release_above_the_floor() -> None:
    choice = choose({"1.8.0": OLD, "1.9.0": OLD, "1.10.0": OLD, "1.7.0": OLD})

    assert (choice.version, choice.major) == ("1.10.0", None)


def test_choose_finds_nothing_when_the_floor_is_the_newest_release() -> None:
    assert choose({"1.7.0": OLD, "1.8.0": OLD}).outputs() == {"version": "", "major": ""}


@pytest.mark.parametrize(
    ("version", "files"),
    [
        pytest.param("1.9.0rc1", OLD, id="pre-release"),
        pytest.param("1.9.0.dev2", OLD, id="development release"),
        pytest.param("1.9.0", [], id="no files"),
        pytest.param("1.9.0", [upload("2026-08-01T10:00:00Z", yanked=True)], id="yanked"),
        pytest.param("1.9.0", [upload("2026-11-23T12:00:01Z")], id="out for under 3 days"),
    ],
)
def test_choose_skips_releases_that_are_not_ready(
    version: str, files: list[dict[str, Any]]
) -> None:
    assert choose({"1.8.0": OLD, version: files}).version is None


def test_choose_takes_a_release_once_it_has_been_out_for_three_days() -> None:
    assert choose({"1.9.0": [upload("2026-11-23T12:00:00Z")]}).version == "1.9.0"


def test_choose_dates_a_release_by_its_first_file_that_is_not_yanked() -> None:
    files = [upload("2026-08-01T10:00:00Z", yanked=True), upload("2026-11-25T10:00:00Z")]

    assert choose({"1.9.0": files}).version is None


def test_choose_treats_a_two_part_version_like_its_three_part_form() -> None:
    assert choose({"1.0": OLD, "1.0.1": OLD}, floor="1.0.0").version == "1.0.1"
    assert choose({"1.0.0": OLD}, floor="1.0").version is None


def test_choose_reports_a_release_at_or_above_the_cap_as_major() -> None:
    choice = choose({"1.9.0": OLD, "2.0": OLD, "2.1.0": OLD})

    assert choice.outputs() == {"version": "1.9.0", "major": "2.1.0"}


def test_read_range_reads_the_floor_and_cap_from_pyproject() -> None:
    assert update_yfinance.read_range(ROOT)[1] == "2"


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    for name in REPO_FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / name, target)
    pyproject = tmp_path / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    text = re.sub(r'(?m)^version = ".*"$', 'version = "0.1.0"', text, count=1)
    text = re.sub(r'"yfinance>=[^"]*"', '"yfinance>=1.7.0,<2"', text)
    pyproject.write_text(text, encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n### Added\n\n- Credits.\n\n"
        "## [0.1.0] - 2026-11-26\n\n### Added\n\n- The first release.\n\n"
        "[Unreleased]: https://example.com/compare/v0.1.0...HEAD\n"
        "[0.1.0]: https://example.com/releases/tag/v0.1.0\n",
        encoding="utf-8",
    )
    return tmp_path


class FakeUv:
    """Stands in for uv: bumps the patch version and rewrites the yfinance requirement."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], cwd: Path, check: bool) -> None:
        self.commands.append(command)
        pyproject = cwd / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        if command[:3] == ["uv", "version", "--bump"]:
            text = text.replace('version = "0.1.0"', 'version = "0.1.1"', 1)
        elif command[:2] == ["uv", "add"]:
            text = re.sub(r'"yfinance>=[^"]*"', f'"{command[2]}"', text)
        pyproject.write_text(text, encoding="utf-8")


def test_apply_requires_the_release_bumps_the_patch_version_and_writes_the_changelog(
    repo_copy: Path,
) -> None:
    uv = FakeUv()

    release = update_yfinance.apply(repo_copy, "1.8.0", uv, "2026-12-01")

    assert release == "0.1.1"
    assert uv.commands[-1] == [
        "uv", "add", "yfinance>=1.8.0,<2", "--upgrade-package", "yfinance", "--no-sync",
    ]  # fmt: skip
    assert update_yfinance.read_range(repo_copy) == ("1.8.0", "2")
    assert update_yfinance.set_version.mismatches(repo_copy) == []
    notes = update_yfinance.release_notes.section(
        (repo_copy / "CHANGELOG.md").read_text(encoding="utf-8"), "0.1.1"
    )
    assert notes == (
        "### Added\n\n- Credits.\n\n### Changed\n\n- Require yfinance 1.8.0 or later "
        "([release notes](https://github.com/ranaroussi/yfinance/releases/tag/1.8.0)).\n"
    )


@pytest.mark.parametrize("version", ["1.7.0", "1.6.0", "2.0.0", "1.9.0rc1"])
def test_apply_refuses_a_version_outside_the_range(repo_copy: Path, version: str) -> None:
    uv = FakeUv()

    with pytest.raises(ValueError, match=version.replace(".", r"\.")):
        update_yfinance.apply(repo_copy, version, uv, "2026-12-01")

    assert uv.commands == []


def test_main_check_writes_the_choice_to_github_output(
    repo_copy: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    github_output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    pypi = {"releases": {"1.7.0": OLD, "1.8.0": OLD, "2.0.0": OLD}}

    code = update_yfinance.main(["check"], root=repo_copy, fetch=lambda url: pypi, now=lambda: NOW)

    assert code == 0
    assert capsys.readouterr().out == "version=1.8.0\nmajor=2.0.0\n"
    assert github_output.read_text(encoding="utf-8") == "version=1.8.0\nmajor=2.0.0\n"


def test_main_apply_reports_the_new_release(
    repo_copy: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    code = update_yfinance.main(["apply", "1.8.0"], root=repo_copy, run=FakeUv(), now=lambda: NOW)

    assert code == 0
    assert capsys.readouterr().out == "release=0.1.1\n"
    assert "## [0.1.1] - 2026-11-26" in (repo_copy / "CHANGELOG.md").read_text(encoding="utf-8")
