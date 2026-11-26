"""Command-line entry point: ``yfinance-agent-mcp`` (also ``python -m yfinance_agent_mcp``)."""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from collections.abc import Sequence

from yfinance_agent_mcp import __version__
from yfinance_agent_mcp.config import LOG_LEVELS, ConfigError, Settings

PROG = "yfinance-agent-mcp"


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, load settings and serve MCP over stdio until the client disconnects."""
    args = _parser().parse_args(argv)
    try:
        settings = Settings.from_env()
    except ConfigError as error:
        print(f"{PROG}: {error}", file=sys.stderr)
        return 2
    if args.log_level:
        settings = dataclasses.replace(settings, log_level=args.log_level)
    # stdout carries the MCP protocol, so every log line goes to stderr.
    logging.basicConfig(
        level=settings.log_level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Imported here so --version answers without loading yfinance and pandas.
    from yfinance_agent_mcp.server import create_server

    try:
        server = create_server(settings)
    except ValueError as error:  # e.g. an unknown YFINANCE_AGENT_MCP_TTL_<CATEGORY>
        print(f"{PROG}: {error}", file=sys.stderr)
        return 2
    server.run()
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Read-only yfinance MCP server for AI trading-research agents (stdio).",
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {__version__}")
    parser.add_argument(
        "--log-level",
        type=str.upper,
        choices=LOG_LEVELS,
        help="log verbosity on stderr; overrides YFINANCE_AGENT_MCP_LOG_LEVEL",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
