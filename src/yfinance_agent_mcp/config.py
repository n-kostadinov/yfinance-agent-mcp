"""Server settings read from ``YFINANCE_AGENT_MCP_*`` environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

ENV_PREFIX = "YFINANCE_AGENT_MCP_"
TTL_PREFIX = f"{ENV_PREFIX}TTL_"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


class ConfigError(ValueError):
    """An environment variable holds a value the server cannot use."""


def _default_cache_dir() -> Path:
    return Path(platformdirs.user_cache_dir("yfinance-agent-mcp", appauthor=False))


@dataclass(frozen=True)
class Settings:
    """Everything the server can be configured with; defaults suit a single personal agent."""

    cache_dir: Path = field(default_factory=_default_cache_dir)
    rate_limit_per_second: float = 2.0
    rate_limit_burst: int = 5
    ttl_overrides: Mapping[str, float] = field(default_factory=dict)
    log_level: str = "WARNING"
    lang: str = "en-US"
    region: str = "US"
    proxy: str | None = None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build settings from environment variables, rejecting unusable values."""
        env = os.environ if environ is None else environ
        defaults = cls()
        cache_dir = env.get(f"{ENV_PREFIX}CACHE_DIR")
        return cls(
            cache_dir=Path(cache_dir) if cache_dir else defaults.cache_dir,
            rate_limit_per_second=_positive_float(
                env, f"{ENV_PREFIX}RATE_LIMIT", defaults.rate_limit_per_second
            ),
            rate_limit_burst=_positive_int(
                env, f"{ENV_PREFIX}RATE_BURST", defaults.rate_limit_burst
            ),
            ttl_overrides=_ttl_overrides(env),
            log_level=_log_level(env, f"{ENV_PREFIX}LOG_LEVEL", defaults.log_level),
            lang=env.get(f"{ENV_PREFIX}LANG") or defaults.lang,
            region=env.get(f"{ENV_PREFIX}REGION") or defaults.region,
            proxy=env.get(f"{ENV_PREFIX}PROXY") or None,
        )


def _positive_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
    if value <= 0:
        raise ConfigError(f"{name} must be greater than 0, got {raw!r}")
    return value


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from None
    if value < 1:
        raise ConfigError(f"{name} must be at least 1, got {raw!r}")
    return value


def _log_level(env: Mapping[str, str], name: str, default: str) -> str:
    raw = env.get(name)
    if raw is None:
        return default
    level = raw.strip().upper()
    if level not in LOG_LEVELS:
        raise ConfigError(f"{name} must be one of {', '.join(LOG_LEVELS)}, got {raw!r}")
    return level


def _ttl_overrides(env: Mapping[str, str]) -> dict[str, float]:
    """Read ``YFINANCE_AGENT_MCP_TTL_<CATEGORY>=<seconds>``; the cache validates the categories."""
    overrides: dict[str, float] = {}
    for name, raw in env.items():
        if not name.startswith(TTL_PREFIX):
            continue
        try:
            seconds = float(raw)
        except ValueError:
            raise ConfigError(f"{name} must be a number of seconds, got {raw!r}") from None
        if seconds < 0:
            raise ConfigError(f"{name} must not be negative, got {raw!r}")
        overrides[name.removeprefix(TTL_PREFIX).lower()] = seconds
    return overrides
