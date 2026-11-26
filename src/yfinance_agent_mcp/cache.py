"""Cache of tool results; every entry expires after its category's time to live.

The server owns freshness: yfinance's own in-process cache never expires, so the gateway
clears it and this cache decides how long a result may be reused.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import TypeVar

T = TypeVar("T")

# Seconds a result stays valid, by category. Override with YFINANCE_AGENT_MCP_TTL_<CATEGORY>.
DEFAULT_TTLS: Mapping[str, float] = MappingProxyType(
    {
        "quotes": 15,
        "history_intraday": 30,
        "history_daily": 300,
        "news": 120,
        "search": 120,
        "market": 30,
        "screen": 60,
        "options": 60,
        "events": 3_600,
        "analysts": 3_600,
        "fundamentals": 21_600,
        "datasets": 21_600,
        "sector": 21_600,
    }
)


class TtlCache:
    """Thread-safe result cache keyed by category and normalized arguments."""

    def __init__(
        self,
        overrides: Mapping[str, float] | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_entries: int = 512,
    ) -> None:
        overrides = overrides or {}
        unknown = sorted(set(overrides) - set(DEFAULT_TTLS))
        if unknown:
            raise ValueError(
                f"unknown cache categories {unknown}; valid categories: {', '.join(DEFAULT_TTLS)}"
            )
        self._ttls = {**DEFAULT_TTLS, **overrides}
        self._clock = clock
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[float, object]] = {}

    def get_or_compute(
        self, category: str, key_args: Mapping[str, object], compute: Callable[[], T]
    ) -> T:
        """Return the cached result for these arguments, or compute and cache it.

        Exceptions from ``compute`` propagate and nothing is cached for them.
        """
        ttl = self._ttls[category]
        key = json.dumps([category, key_args], sort_keys=True, default=str)
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry[0] > self._clock():
                return entry[1]  # type: ignore[return-value]
        value = compute()
        if ttl > 0:
            with self._lock:
                self._entries.pop(key, None)
                self._entries[key] = (self._clock() + ttl, value)
                self._evict_over_capacity()
        return value

    def _evict_over_capacity(self) -> None:
        if len(self._entries) <= self._max_entries:
            return
        now = self._clock()
        for key in [k for k, (expires_at, _) in self._entries.items() if expires_at <= now]:
            del self._entries[key]
        while len(self._entries) > self._max_entries:
            del self._entries[next(iter(self._entries))]
