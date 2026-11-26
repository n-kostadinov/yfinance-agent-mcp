from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[2]

CHANGELOG = """\
# Changelog

All notable changes are documented here.

## [Unreleased]

## [1.1.0] - 2026-12-01

### Fixed

- Quotes for [delisted symbols][issue-7] report `not_found`.

[issue-7]: https://example.com/issues/7

## [1.0.0] - 2026-11-24

### Added

- The first release.

[Unreleased]: https://example.com/compare/v1.1.0...HEAD
[1.1.0]: https://example.com/compare/v1.0.0...v1.1.0
[1.0.0]: https://example.com/releases/tag/v1.0.0
"""


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "release_notes", ROOT / "scripts" / "release_notes.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release_notes = load_script()


def write_changelog(root: Path) -> None:
    (root / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")


def test_section_stops_at_the_next_version_heading() -> None:
    assert release_notes.section(CHANGELOG, "1.1.0") == (
        "### Fixed\n"
        "\n"
        "- Quotes for [delisted symbols][issue-7] report `not_found`.\n"
        "\n"
        "[issue-7]: https://example.com/issues/7\n"
    )


def test_section_leaves_out_the_version_links_at_the_bottom() -> None:
    assert release_notes.section(CHANGELOG, "1.0.0") == "### Added\n\n- The first release.\n"


def test_section_accepts_a_tag_with_a_leading_v() -> None:
    assert release_notes.section(CHANGELOG, "v1.0.0") == "### Added\n\n- The first release.\n"


def test_section_for_an_unknown_version_raises_lookup_error() -> None:
    with pytest.raises(LookupError, match=r"no section for version 2\.0\.0"):
        release_notes.section(CHANGELOG, "2.0.0")


def test_empty_section_raises_lookup_error() -> None:
    with pytest.raises(LookupError, match="section for version Unreleased is empty"):
        release_notes.section(CHANGELOG, "Unreleased")


def test_main_prints_the_notes_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_changelog(tmp_path)

    assert release_notes.main(["v1.0.0"], root=tmp_path) == 0

    assert capsys.readouterr().out == "### Added\n\n- The first release.\n"


def test_main_reports_a_missing_section_and_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_changelog(tmp_path)

    assert release_notes.main(["v9.9.9"], root=tmp_path) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "no section for version 9.9.9" in captured.err


def test_repository_changelog_has_notes_for_the_pyproject_version() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    notes = release_notes.section(changelog, pyproject["project"]["version"])

    assert notes.startswith("### ")
