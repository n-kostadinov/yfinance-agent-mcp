"""Adopt a new yfinance release: find it on PyPI, then prepare a patch release that needs it.

python3 scripts/update_yfinance.py check          # version=1.9.0 (or empty), major=2.0.0 (or empty)
python3 scripts/update_yfinance.py apply 1.9.0    # raise the floor, bump, write the CHANGELOG

Both print key=value lines and append them to $GITHUB_OUTPUT when it is set. A release
counts once it has files on PyPI, is not yanked, and has been out for COOL_DOWN, so a
broken or compromised upload has time to be pulled before it reaches a release.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tomllib
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import release_notes
import set_version

ROOT = Path(__file__).resolve().parents[1]
PYPI_URL = "https://pypi.org/pypi/yfinance/json"
RELEASE_NOTES_URL = "https://github.com/ranaroussi/yfinance/releases/tag/{version}"
COOL_DOWN = timedelta(days=3)
_REQUIREMENT = re.compile(r"^yfinance>=(?P<floor>[^,]+),<(?P<cap>[^,]+)$")
_FINAL_RELEASE = re.compile(r"^\d+(\.\d+)*$")
Fetch = Callable[[str], Any]
Runner = set_version.Runner


@dataclass(frozen=True)
class Choice:
    """What ``check`` found: a release to adopt, and a release at or above the cap."""

    version: str | None
    major: str | None

    def outputs(self) -> dict[str, str]:
        return {"version": self.version or "", "major": self.major or ""}


def read_range(root: Path) -> tuple[str, str]:
    """The (floor, cap) of the ``yfinance>=floor,<cap`` requirement in pyproject.toml."""
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    for requirement in pyproject["project"]["dependencies"]:
        match = _REQUIREMENT.match(requirement.replace(" ", ""))
        if match:
            return match["floor"], match["cap"]
    raise ValueError('pyproject.toml has no "yfinance>=X,<Y" dependency')


def choose(
    releases: Mapping[str, Sequence[Mapping[str, Any]]], floor: str, cap: str, now: datetime
) -> Choice:
    """Pick the newest usable release inside (floor, cap), and the newest one at or above cap.

    ``releases`` is PyPI's JSON ``releases`` mapping: version -> list of uploaded files.
    """
    usable = sorted(
        (version for version, files in releases.items() if _is_usable(version, files, now)),
        key=_sort_key,
    )
    inside = [v for v in usable if _sort_key(floor) < _sort_key(v) < _sort_key(cap)]
    beyond = [v for v in usable if _sort_key(v) >= _sort_key(cap)]
    return Choice(version=inside[-1] if inside else None, major=beyond[-1] if beyond else None)


def check(root: Path, fetch: Fetch, now: datetime) -> Choice:
    floor, cap = read_range(root)
    return choose(fetch(PYPI_URL)["releases"], floor, cap, now)


def apply(root: Path, version: str, run: Runner, today: str) -> str:
    """Require yfinance ``version``, bump the patch version and write its CHANGELOG section.

    Returns the new project version. The bump comes first because ``uv add`` re-locks,
    which also records the new project version in uv.lock.
    """
    floor, cap = read_range(root)
    if not (_FINAL_RELEASE.match(version) and _sort_key(floor) < _sort_key(version)):
        raise ValueError(f"yfinance {version} is not a final release newer than {floor}")
    if _sort_key(version) >= _sort_key(cap):
        raise ValueError(f"yfinance {version} is not below the cap {cap}")
    release = set_version.bump(root, "patch", run=run)
    run(
        ["uv", "add", f"yfinance>={version},<{cap}", "--upgrade-package", "yfinance", "--no-sync"],
        cwd=root,
        check=True,
    )
    change = (
        f"Require yfinance {version} or later "
        f"([release notes]({RELEASE_NOTES_URL.format(version=version)}))."
    )
    changelog = root / "CHANGELOG.md"
    text = release_notes.add_release(changelog.read_text(encoding="utf-8"), release, today, change)
    changelog.write_text(text, encoding="utf-8", newline="\n")
    return release


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "yfinance-agent-mcp-updater"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main(
    argv: Sequence[str] | None = None,
    root: Path = ROOT,
    fetch: Fetch = fetch_json,
    run: Runner = subprocess.run,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="find a newer yfinance release on PyPI")
    adopt = commands.add_parser("apply", help="require a yfinance release and bump the version")
    adopt.add_argument("version")
    args = parser.parse_args(argv)
    if args.command == "check":
        outputs = check(root, fetch, now()).outputs()
    else:
        outputs = {"release": apply(root, args.version, run, now().date().isoformat())}
    _report(outputs)
    return 0


def _is_usable(version: str, files: Sequence[Mapping[str, Any]], now: datetime) -> bool:
    """A final release with at least one file that is not yanked, out for COOL_DOWN."""
    available = [file for file in files if not file.get("yanked", False)]
    if not _FINAL_RELEASE.match(version) or not available:
        return False
    uploaded = min(datetime.fromisoformat(file["upload_time_iso_8601"]) for file in available)
    return now - uploaded >= COOL_DOWN


def _sort_key(version: str) -> tuple[int, ...]:
    """Compare final releases numerically; ``1.0`` and ``1.0.0`` are the same release."""
    parts = [int(part) for part in version.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def _report(outputs: Mapping[str, str]) -> None:
    lines = "".join(f"{key}={value}\n" for key, value in outputs.items())
    print(lines, end="")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as output:
            output.write(lines)


if __name__ == "__main__":
    raise SystemExit(main())
