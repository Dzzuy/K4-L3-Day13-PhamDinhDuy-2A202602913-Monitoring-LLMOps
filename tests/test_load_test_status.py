from __future__ import annotations

import httpx

from scripts.load_test import send_request


PAYLOAD = {"user_id": "u01", "session_id": "s01", "feature": "qa", "message": "hello"}


def test_load_test_reports_http_failure() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503, json={"detail": "unavailable"}))
    with httpx.Client(transport=transport) as client:
        assert send_request(client, PAYLOAD) is False


def test_load_test_reports_connection_failure() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable", request=request)

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        assert send_request(client, PAYLOAD) is False
