"""Process-wide pacing of Yahoo requests: a token bucket plus a pause after HTTP 429.

Yahoo throttles by IP address, so one limiter guards every request the process makes.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class CooldownActive(Exception):
    """Requests are paused after Yahoo answered HTTP 429; retry after ``retry_after`` seconds."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Yahoo rate limit cool-down active; retry in {retry_after:.0f} s")
        self.retry_after = retry_after


class RateLimiter:
    """Allows ``burst`` requests at once, then ``rate_per_second``; pauses all after a 429."""

    def __init__(
        self,
        rate_per_second: float,
        burst: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        first_pause: float = 30.0,
        max_pause: float = 300.0,
    ) -> None:
        self._rate = rate_per_second
        self._burst = float(burst)
        self._clock = clock
        self._sleep = sleep
        self._first_pause = first_pause
        self._max_pause = max_pause
        self._lock = threading.Lock()
        self._tokens = float(burst)
        self._refilled_at = clock()
        self._paused_until = float("-inf")
        self._next_pause = first_pause

    def acquire(self) -> None:
        """Take one request slot, sleeping until it is free.

        Raises ``CooldownActive`` while requests are paused after a 429.
        """
        with self._lock:
            now = self._clock()
            remaining = self._paused_until - now
            if remaining > 0:
                raise CooldownActive(remaining)
            elapsed = now - self._refilled_at
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._refilled_at = now
            # Reserve the slot now (tokens may go negative) so concurrent callers queue behind it.
            wait = max(0.0, (1 - self._tokens) / self._rate)
            self._tokens -= 1
        if wait > 0:
            self._sleep(wait)

    def report_rate_limited(self) -> float:
        """Record an HTTP 429 and return how long requests are paused.

        Consecutive 429s double the pause up to ``max_pause``; a 429 that arrives while a pause
        is already running (from a concurrent request) does not lengthen it.
        """
        with self._lock:
            now = self._clock()
            if self._paused_until > now:
                return self._paused_until - now
            pause = self._next_pause
            self._paused_until = now + pause
            self._next_pause = min(pause * 2, self._max_pause)
            return pause

    def report_success(self) -> None:
        """Record a successful response, so the next pause starts at ``first_pause`` again."""
        with self._lock:
            self._next_pause = self._first_pause

    def cooldown_remaining(self) -> float:
        """Seconds until requests are allowed again; 0 when not paused."""
        with self._lock:
            return max(0.0, self._paused_until - self._clock())
