from __future__ import annotations

import pandas as pd
import pytest

from tests.fakes import FakeGateway
from yfinance_agent_mcp.errors import InvalidArgument, NotFound
from yfinance_agent_mcp.gateway import OptionChain
from yfinance_agent_mcp.tools.options import build_options

EXPIRATIONS = ["2026-11-28", "2026-12-05", "2026-12-19"]


def chain_side(strikes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "contractSymbol": [f"AAPL261128C{int(s):05d}" for s in strikes],
            "lastTradeDate": [pd.Timestamp("2026-11-24 15:30", tz="UTC")] * len(strikes),
            "strike": strikes,
            "lastPrice": [1.0] * len(strikes),
            "bid": [0.9] * len(strikes),
            "ask": [1.1] * len(strikes),
            "change": [0.1] * len(strikes),
            "percentChange": [10.0] * len(strikes),
            "volume": [100.0] * len(strikes),
            "openInterest": [1_000.0] * len(strikes),
            "impliedVolatility": [0.3] * len(strikes),
            "inTheMoney": [False] * len(strikes),
            "contractSize": ["REGULAR"] * len(strikes),
            "currency": ["USD"] * len(strikes),
        }
    )


def options_gateway(spot: float = 40.5, strikes: int = 80) -> FakeGateway:
    gateway = FakeGateway()
    gateway.expirations["AAPL"] = EXPIRATIONS
    side = chain_side([float(s) for s in range(1, strikes + 1)])
    for expiry in EXPIRATIONS:
        gateway.chains[("AAPL", expiry)] = OptionChain(
            calls=side, puts=side, underlying={"regularMarketPrice": spot}
        )
    return gateway


def test_nearest_expiry_is_used_by_default() -> None:
    result = build_options(options_gateway(), "AAPL", None, 10)

    assert (result.expiry, result.expirations) == ("2026-11-28", EXPIRATIONS)


def test_chain_keeps_ten_strikes_on_each_side_of_the_price() -> None:
    result = build_options(options_gateway(spot=40.5), "AAPL", "2026-12-05", 10)

    assert [row["strike"] for row in result.calls] == [float(s) for s in range(31, 51)]
    assert [row["strike"] for row in result.puts] == [float(s) for s in range(31, 51)]
    assert result.underlying_price == 40.5


def test_rows_keep_the_columns_that_matter_with_readable_keys() -> None:
    row = build_options(options_gateway(), "AAPL", None, 1).calls[0]

    assert set(row) == {
        "contract_symbol",
        "strike",
        "last_price",
        "bid",
        "ask",
        "change_pct",
        "volume",
        "open_interest",
        "implied_volatility",
        "in_the_money",
        "last_trade_date",
    }


def test_unknown_expiry_lists_the_valid_dates() -> None:
    with pytest.raises(InvalidArgument, match="2026-11-28, 2026-12-05, 2026-12-19"):
        build_options(options_gateway(), "AAPL", "2027-01-01", 10)


def test_symbol_without_options_is_not_found() -> None:
    with pytest.raises(NotFound, match="no listed options"):
        build_options(FakeGateway(), "BTC-USD", None, 10)
