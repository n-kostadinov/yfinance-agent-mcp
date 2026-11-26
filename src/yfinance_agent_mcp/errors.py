"""Failures an agent can act on, each turned into an MCP tool error with clear advice.

The gateway raises these instead of letting yfinance return empty results, and the tools
convert them with ``to_tool_error`` so the model reads ``<code>: <what happened and what to do>``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from mcp.server.mcpserver.exceptions import ToolError


class DomainError(Exception):
    """Base class; ``code`` is the machine-readable kind of failure."""

    code = "error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def to_tool_error(self) -> ToolError:
        return ToolError(f"{self.code}: {self.message}")


class RateLimited(DomainError):
    """Yahoo answered HTTP 429, or the server is pausing requests after one."""

    code = "rate_limited"

    def __init__(self, retry_after: float) -> None:
        self.retry_after = max(1, math.ceil(retry_after))
        super().__init__(
            f"Yahoo Finance is rate-limiting this server. Retry in {self.retry_after} s, "
            "and batch symbols into fewer calls."
        )


class NotFound(DomainError):
    """Yahoo has no data for the request (unknown or delisted symbol, empty range)."""

    code = "not_found"


class InvalidArgument(DomainError):
    """The request cannot be answered as asked; ``valid_values`` lists what would work."""

    code = "invalid_argument"

    def __init__(self, message: str, valid_values: Sequence[str] = ()) -> None:
        self.valid_values = tuple(valid_values)
        hint = f". Valid values: {', '.join(self.valid_values)}." if self.valid_values else ""
        super().__init__(f"{message.rstrip('.')}{hint}" if hint else message)


class UpstreamError(DomainError):
    """Yahoo or the network failed in a way a retry may fix."""

    code = "upstream_error"

    def __init__(self, message: str) -> None:
        super().__init__(
            f"{message}. Retry later; if this keeps happening, Yahoo may have changed its API "
            "(check for a yfinance-agent-mcp update)."
        )
