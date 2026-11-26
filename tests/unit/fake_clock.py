"""A controllable clock for tests of time-dependent behavior."""

from __future__ import annotations


class FakeClock:
    """Monotonic time that only moves when a test advances it or something sleeps on it."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
