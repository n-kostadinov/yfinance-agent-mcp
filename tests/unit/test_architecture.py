from __future__ import annotations

import re
from pathlib import Path

PACKAGE = Path(__file__).parents[2] / "src" / "yfinance_agent_mcp"
YFINANCE_IMPORT = re.compile(r"^\s*(import yfinance\b|from yfinance\b)", re.MULTILINE)


def test_only_the_gateway_imports_yfinance() -> None:
    importers = sorted(
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*.py")
        if YFINANCE_IMPORT.search(path.read_text(encoding="utf-8"))
    )

    assert importers == ["gateway.py"]
