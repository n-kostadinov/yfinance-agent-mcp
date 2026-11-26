from __future__ import annotations

import pytest
import requests
from curl_cffi import requests as curl_requests


@pytest.mark.parametrize("session_factory", [requests.Session, curl_requests.Session])
def test_offline_tests_cannot_reach_the_network(session_factory: type) -> None:
    session = session_factory()

    with pytest.raises(RuntimeError, match="offline test attempted a real HTTP request"):
        session.get("https://query1.finance.yahoo.com/v1/test/getcrumb")
