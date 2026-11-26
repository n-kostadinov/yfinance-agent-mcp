from __future__ import annotations

from pathlib import Path

import pytest

from yfinance_agent_mcp.config import ConfigError, Settings

PREFIX = "YFINANCE_AGENT_MCP_"


def test_defaults_apply_when_no_variables_are_set() -> None:
    settings = Settings.from_env({})

    assert settings.rate_limit_per_second == 2.0
    assert settings.rate_limit_burst == 5
    assert settings.log_level == "WARNING"
    assert (settings.lang, settings.region) == ("en-US", "US")
    assert settings.proxy is None
    assert dict(settings.ttl_overrides) == {}
    assert "yfinance-agent-mcp" in settings.cache_dir.parts


def test_variables_override_every_default(tmp_path: Path) -> None:
    env = {
        f"{PREFIX}CACHE_DIR": str(tmp_path),
        f"{PREFIX}RATE_LIMIT": "0.5",
        f"{PREFIX}RATE_BURST": "2",
        f"{PREFIX}LOG_LEVEL": "debug",
        f"{PREFIX}LANG": "de-DE",
        f"{PREFIX}REGION": "DE",
        f"{PREFIX}PROXY": "http://proxy.local:8080",
        f"{PREFIX}TTL_QUOTES": "5",
        f"{PREFIX}TTL_NEWS": "0",
        "UNRELATED_VARIABLE": "ignored",
    }

    settings = Settings.from_env(env)

    assert settings == Settings(
        cache_dir=tmp_path,
        rate_limit_per_second=0.5,
        rate_limit_burst=2,
        ttl_overrides={"quotes": 5.0, "news": 0.0},
        log_level="DEBUG",
        lang="de-DE",
        region="DE",
        proxy="http://proxy.local:8080",
    )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        (f"{PREFIX}RATE_LIMIT", "0"),
        (f"{PREFIX}RATE_LIMIT", "fast"),
        (f"{PREFIX}RATE_BURST", "0"),
        (f"{PREFIX}RATE_BURST", "1.5"),
        (f"{PREFIX}LOG_LEVEL", "LOUD"),
        (f"{PREFIX}TTL_QUOTES", "-1"),
        (f"{PREFIX}TTL_QUOTES", "soon"),
    ],
)
def test_invalid_value_is_rejected_with_the_variable_name(name: str, value: str) -> None:
    with pytest.raises(ConfigError, match=name):
        Settings.from_env({name: value})
