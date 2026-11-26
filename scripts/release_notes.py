"""Print the CHANGELOG.md section for one version, used as the GitHub Release notes.

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


if __name__ == "__main__":
    raise SystemExit(main())
