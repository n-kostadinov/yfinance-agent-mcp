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


UNRELEASED = """\
# Changelog

## [Unreleased]

### Added

- A new tool.

### Fixed

- A crash.

## [1.0.0] - 2026-11-24

### Added

- The first release.

[Unreleased]: https://example.com/compare/v1.0.0...HEAD
[1.0.0]: https://example.com/releases/tag/v1.0.0
"""

CHANGE = "Require yfinance 1.9.0 or later."


def test_add_release_moves_the_unreleased_entries_and_puts_changed_before_fixed() -> None:
    changelog = release_notes.add_release(UNRELEASED, "1.0.1", "2026-12-01", CHANGE)

    assert "## [Unreleased]\n\n## [1.0.1] - 2026-12-01\n\n### Added" in changelog
    assert release_notes.section(changelog, "1.0.1") == (
        "### Added\n\n- A new tool.\n\n### Changed\n\n- Require yfinance 1.9.0 or later.\n\n"
        "### Fixed\n\n- A crash.\n"
    )
    assert release_notes.section(changelog, "1.0.0") == "### Added\n\n- The first release.\n"


def test_add_release_adds_to_an_existing_changed_subsection() -> None:
    changelog = UNRELEASED.replace("### Fixed\n\n- A crash.", "### Changed\n\n- Faster quotes.")

    released = release_notes.add_release(changelog, "1.0.1", "2026-12-01", CHANGE)

    assert release_notes.section(released, "1.0.1") == (
        "### Added\n\n- A new tool.\n\n### Changed\n\n- Faster quotes.\n"
        "- Require yfinance 1.9.0 or later.\n"
    )


def test_add_release_with_nothing_unreleased_lists_only_the_change() -> None:
    changelog = UNRELEASED.replace("### Added\n\n- A new tool.\n\n### Fixed\n\n- A crash.\n\n", "")

    released = release_notes.add_release(changelog, "1.0.1", "2026-12-01", CHANGE)

    assert release_notes.section(released, "1.0.1") == f"### Changed\n\n- {CHANGE}\n"


def test_add_release_points_the_comparison_links_at_the_new_version() -> None:
    changelog = release_notes.add_release(UNRELEASED, "1.0.1", "2026-12-01", CHANGE)

    assert changelog.endswith(
        "[Unreleased]: https://example.com/compare/v1.0.1...HEAD\n"
        "[1.0.1]: https://example.com/compare/v1.0.0...v1.0.1\n"
        "[1.0.0]: https://example.com/releases/tag/v1.0.0\n"
    )


def test_add_release_without_an_unreleased_section_raises_lookup_error() -> None:
    with pytest.raises(LookupError, match=r"no \[Unreleased\] section"):
        release_notes.add_release(CHANGELOG.replace("## [Unreleased]\n", ""), "1.1.1", "x", CHANGE)
