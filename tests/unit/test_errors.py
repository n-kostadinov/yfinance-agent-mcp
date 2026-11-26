from __future__ import annotations

import pytest

from yfinance_agent_mcp.errors import (
    DomainError,
    InvalidArgument,
    NotFound,
    RateLimited,
    UpstreamError,
)


@pytest.mark.parametrize(
    ("error", "expected_parts"),
    [
        (RateLimited(12.3), ["rate_limited:", "Retry in 13 s", "fewer calls"]),
        (NotFound("$XYZ: no price data found"), ["not_found:", "$XYZ: no price data found"]),
        (
            InvalidArgument("unknown dataset 'holders'", ["major_holders", "insider_trades"]),
            ["invalid_argument:", "unknown dataset 'holders'", "major_holders, insider_trades"],
        ),
        (UpstreamError("Yahoo returned HTTP 503"), ["upstream_error:", "HTTP 503", "Retry later"]),
    ],
)
def test_error_becomes_a_tool_error_with_its_code_and_advice(
    error: DomainError, expected_parts: list[str]
) -> None:
    message = str(error.to_tool_error())

    for part in expected_parts:
        assert part in message


def test_rate_limit_retry_time_is_at_least_one_second() -> None:
    assert RateLimited(0.2).retry_after == 1
