"""One live price stream shared by all calls, remembering the latest tick of each symbol.

Symbols are subscribed on first request and unsubscribed once nobody has asked for them in
``idle_after``. With yfinance raising instead of hiding errors, a dropped connection ends the
listener; the next request opens a new stream and subscribes the symbols again.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from yfinance_agent_mcp.errors import DomainError, UpstreamError
from yfinance_agent_mcp.gateway import LiveStream

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Tick:
    """A decoded message from the feed and when the server received it."""

    message: Mapping[str, Any]
    received_at: datetime


class LiveQuotes:
    def __init__(
        self,
        open_stream: Callable[[], LiveStream],
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        idle_after: timedelta = timedelta(minutes=10),
    ) -> None:
        self._open_stream = open_stream
        self._now = now
        self._idle_after = idle_after
        self._stream: LiveStream | None = None
        self._listener: asyncio.Task[None] | None = None
        self._subscribed: set[str] = set()
        self._last_asked: dict[str, datetime] = {}
        self._ticks: dict[str, Tick] = {}
        self._tick_arrived = asyncio.Event()
        self._lock = asyncio.Lock()

    async def latest(
        self, symbols: Sequence[str], wait_seconds: float
    ) -> tuple[dict[str, Tick], list[str]]:
        """Latest tick per symbol, waiting up to ``wait_seconds`` for symbols without one."""
        async with self._lock:
            now = self._now()
            self._last_asked.update(dict.fromkeys(symbols, now))
            try:
                stream = await self._subscribe(symbols)
                await self._unsubscribe_idle(stream, now)
            except DomainError:
                raise
            except Exception as error:
                raise UpstreamError(f"live price stream failed: {error}") from error
        await self._wait_for(symbols, wait_seconds)
        ticks = {symbol: self._ticks[symbol] for symbol in symbols if symbol in self._ticks}
        return ticks, [symbol for symbol in symbols if symbol not in ticks]

    async def aclose(self) -> None:
        """Stop listening and close the connection; the next request reconnects."""
        await self._stop()
        self._subscribed.clear()

    async def _subscribe(self, symbols: Sequence[str]) -> LiveStream:
        """Subscribe the symbols, reconnecting with all subscriptions if the stream dropped.

        Subscribing before listening matters: both connect when there is no connection yet,
        so a listener started first would read from a different socket than the subscription.
        """
        stream = self._stream
        if stream is None or not self._listening():
            if self._listener is not None and not self._listener.cancelled():
                logger.warning(
                    "live price stream stopped (%r); reconnecting", self._listener.exception()
                )
            await self._stop()
            stream = self._open_stream()
            self._stream = stream
            pending = sorted(self._subscribed | set(symbols))
        else:
            pending = [symbol for symbol in symbols if symbol not in self._subscribed]
        if pending:
            await stream.subscribe(pending)
            self._subscribed.update(pending)
        if not self._listening():
            self._listener = asyncio.create_task(stream.listen(self._on_message))
        return stream

    def _listening(self) -> bool:
        return self._listener is not None and not self._listener.done()

    def _on_message(self, message: Mapping[str, Any]) -> None:
        # Must not raise: with yfinance raising errors, an exception here would end the feed.
        symbol = message.get("id")
        if isinstance(symbol, str):
            self._ticks[symbol] = Tick(message=message, received_at=self._now())
            self._tick_arrived.set()

    async def _unsubscribe_idle(self, stream: LiveStream, now: datetime) -> None:
        idle = sorted(
            symbol
            for symbol in self._subscribed
            if now - self._last_asked.get(symbol, now) >= self._idle_after
        )
        if not idle:
            return
        await stream.unsubscribe(idle)
        self._subscribed.difference_update(idle)
        for symbol in idle:
            self._ticks.pop(symbol, None)
            self._last_asked.pop(symbol, None)

    async def _wait_for(self, symbols: Sequence[str], wait_seconds: float) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait_seconds
        while any(symbol not in self._ticks for symbol in symbols):
            remaining = deadline - loop.time()
            if remaining <= 0:
                return
            self._tick_arrived.clear()
            try:
                await asyncio.wait_for(self._tick_arrived.wait(), remaining)
            except TimeoutError:
                return

    async def _stop(self) -> None:
        listener, stream = self._listener, self._stream
        self._listener, self._stream = None, None
        if listener is not None and not listener.done():
            listener.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await listener
        if stream is not None:
            with contextlib.suppress(Exception):
                await stream.close()
