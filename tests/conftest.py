"""Shared test configuration: the anyio backend and the offline network guard."""

from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _block_real_http(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail fast when an offline test tries to reach Yahoo through curl_cffi or requests."""
    if request.node.get_closest_marker("live"):
        return

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError(
            "offline test attempted a real HTTP request; "
            "fake the transport or mark the test @pytest.mark.live"
        )

    monkeypatch.setattr("curl_cffi.requests.Session.request", refuse)
    monkeypatch.setattr("requests.Session.request", refuse)
