"""Print the CHANGELOG.md section for one version, used as the GitHub Release notes.

The module also owns writing a release section (``add_release``), which the automatic
yfinance updates use.

uv run python scripts/release_notes.py 0.1.0             # or v0.1.0
uv run python scripts/release_notes.py v0.1.0 > notes.md

Exits 1, with the reason on stderr, when the section is missing or empty, so the release
workflow stops before anything is published.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_HEADING = re.compile(r"^## \[(?P<version>[^\]]+)\]")
_LINK_DEFINITION = re.compile(r"^\[(?P<label>[^\]]+)\]:\s")
_UNRELEASED_LINK = re.compile(
    r"^\[Unreleased\]:\s*(?P<base>\S+)/compare/(?P<previous>\S+)\.\.\.HEAD$"
)
# Keep a Changelog's order of change types; a new "### Changed" goes before these.
_AFTER_CHANGED = ("Deprecated", "Removed", "Fixed", "Security")


def section(changelog: str, version: str) -> str:
    """The body of the ``## [version]`` section, without the version comparison links.

    Raises LookupError when the changelog has no section for ``version`` or it is empty.
    """
    version = version.removeprefix("v")
    lines = changelog.splitlines()
    headings = _headings(lines)
    if version not in headings:
        raise LookupError(f"CHANGELOG.md has no section for version {version}")
    start = headings[version] + 1
    end = min((line for line in headings.values() if line >= start), default=len(lines))
    body = [line for line in lines[start:end] if not _is_version_link(line, headings)]
    notes = "\n".join(body).strip()
    if not notes:
        raise LookupError(f"the CHANGELOG.md section for version {version} is empty")
    return notes + "\n"


def add_release(changelog: str, version: str, date: str, change: str) -> str:
    """Release the ``[Unreleased]`` entries as ``## [version] - date``, adding ``change``.

    ``change`` becomes an item under ``### Changed``. The ``[Unreleased]`` comparison link
    moves to the new version, and a link for the new version is added. Raises LookupError
    when the changelog has no ``[Unreleased]`` section or comparison link.
    """
    lines = changelog.splitlines()
    headings = _headings(lines)
    if "Unreleased" not in headings:
        raise LookupError("CHANGELOG.md has no [Unreleased] section")
    start = headings["Unreleased"] + 1
    end = min((line for line in headings.values() if line >= start), default=len(lines))
    entries = _with_change(lines[start:end], change)
    released = [*lines[:start], "", f"## [{version}] - {date}", "", *entries, "", *lines[end:]]
    return "\n".join(_with_version_links(released, version)) + "\n"


def main(argv: Sequence[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("version", help="release version or tag, for example 0.1.0 or v0.1.0")
    args = parser.parse_args(argv)
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    try:
        notes = section(changelog, args.version)
    except LookupError as error:
        print(error, file=sys.stderr)
        return 1
    sys.stdout.write(notes)
    return 0


def _headings(lines: Sequence[str]) -> dict[str, int]:
    """Map each ``## [version]`` heading to its line index."""
    headings: dict[str, int] = {}
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match:
            headings[match["version"]] = index
    return headings


def _is_version_link(line: str, versions: dict[str, int]) -> bool:
    """True for the ``[0.1.0]: https://...`` link definitions behind the version headings."""
    match = _LINK_DEFINITION.match(line)
    return match is not None and match["label"] in versions


def _with_change(entries: Sequence[str], change: str) -> list[str]:
    """Add ``- change`` to the ``### Changed`` subsection, creating it in its usual place."""
    entries = _trimmed(entries)
    item = f"- {change}"
    subsections = [index for index, line in enumerate(entries) if line.startswith("### ")]
    for index in subsections:
        if entries[index].strip() == "### Changed":
            following = next((line for line in subsections if line > index), len(entries))
            end = index + 1 + len(_trimmed(entries[index + 1 : following], leading=False))
            return [*entries[:end], item, *entries[end:]]
    later = next(
        (i for i in subsections if entries[i].removeprefix("### ").strip() in _AFTER_CHANGED),
        len(entries),
    )
    before, after = _trimmed(entries[:later]), entries[later:]
    return [
        *before,
        *([""] if before else []),
        "### Changed",
        "",
        item,
        *([""] if after else []),
        *after,
    ]


def _with_version_links(lines: Sequence[str], version: str) -> list[str]:
    """Point ``[Unreleased]`` at ``vversion...HEAD`` and add the ``[version]`` comparison."""
    for index, line in enumerate(lines):
        match = _UNRELEASED_LINK.match(line)
        if match:
            base, previous = match["base"], match["previous"]
            return [
                *lines[:index],
                f"[Unreleased]: {base}/compare/v{version}...HEAD",
                f"[{version}]: {base}/compare/{previous}...v{version}",
                *lines[index + 1 :],
            ]
    raise LookupError("CHANGELOG.md has no [Unreleased]: .../compare/vX.Y.Z...HEAD link")


def _trimmed(lines: Sequence[str], leading: bool = True) -> list[str]:
    """``lines`` without blank lines at the end (and, if ``leading``, at the start)."""
    kept = list(lines)
    while kept and not kept[-1].strip():
        kept.pop()
    while leading and kept and not kept[0].strip():
        kept.pop(0)
    return kept


if __name__ == "__main__":
    raise SystemExit(main())
