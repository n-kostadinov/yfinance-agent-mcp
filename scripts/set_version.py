"""Keep every file that names the release version in step with pyproject.toml.

uv run python scripts/set_version.py --bump patch    # uv version --bump, then sync files
uv run python scripts/set_version.py --check         # exit 1 if any file disagrees
uv run python scripts/set_version.py --check-tag v0.1.0
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "yfinance-agent-mcp"
Runner = Callable[..., object]


def read_version(root: Path) -> str:
    """The single source of truth: [project].version in pyproject.toml."""
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(pyproject["project"]["version"])


def _versioned_fields(
    root: Path,
) -> Iterator[tuple[str, dict[str, Any], str, Callable[[str], None]]]:
    """Yield (file, parsed JSON, version found, setter) for every place that names the version."""
    server = _load(root, "server.json")
    package = server["packages"][0]
    yield "server.json", server, server["version"], lambda v: server.update(version=v)
    yield "server.json", server, package["version"], lambda v: package.update(version=v)

    marketplace = _load(root, ".claude-plugin/marketplace.json")
    entry = marketplace["plugins"][0]
    yield (
        ".claude-plugin/marketplace.json",
        marketplace,
        entry["version"],
        lambda v: entry.update(version=v),
    )

    plugin = _load(root, "plugins/yfinance/.claude-plugin/plugin.json")
    yield (
        "plugins/yfinance/.claude-plugin/plugin.json",
        plugin,
        plugin["version"],
        lambda v: plugin.update(version=v),
    )

    mcp = _load(root, "plugins/yfinance/.mcp.json")
    server_entry = mcp["mcpServers"]["yfinance"]
    pinned = server_entry["args"][0].partition("@")[2]
    yield (
        "plugins/yfinance/.mcp.json",
        mcp,
        pinned,
        lambda v: server_entry.update(args=[f"{PACKAGE}@{v}"]),
    )


def write_version(root: Path, version: str) -> None:
    """Write ``version`` into every versioned JSON file (pyproject.toml is left to uv)."""
    documents: dict[str, dict[str, Any]] = {}
    for name, document, _found, set_to in _versioned_fields(root):
        set_to(version)
        documents[name] = document
    for name, document in documents.items():
        text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        (root / name).write_text(text, encoding="utf-8")


def mismatches(root: Path, tag: str | None = None) -> list[str]:
    """Every file (and the release tag, if given) that disagrees with pyproject.toml."""
    version = read_version(root)
    problems = [
        f"{name} version is {found}, pyproject.toml has {version}"
        for name, _document, found, _set_to in _versioned_fields(root)
        if found != version
    ]
    if tag is not None and tag.removeprefix("v") != version:
        problems.append(f"tag {tag} does not match pyproject.toml version {version}")
    return list(dict.fromkeys(problems))


def bump(root: Path, part: str, run: Runner = subprocess.run) -> str:
    """Bump pyproject.toml with ``uv version --bump`` and copy the result everywhere else."""
    run(["uv", "version", "--bump", part, "--frozen"], cwd=root, check=True)
    version = read_version(root)
    write_version(root, version)
    return version


def main(argv: Sequence[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--bump", choices=("major", "minor", "patch"))
    action.add_argument("--check", action="store_true")
    action.add_argument("--check-tag", metavar="TAG")
    args = parser.parse_args(argv)
    if args.bump:
        print(f"version is now {bump(root, args.bump)}")
        return 0
    problems = mismatches(root, tag=args.check_tag)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


def _load(root: Path, name: str) -> dict[str, Any]:
    return json.loads((root / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
