from __future__ import annotations

import asyncio
import json
import re

import httpx

from app import logging_config
from app.main import app


def test_request_ids_and_context_are_isolated(monkeypatch, tmp_path) -> None:
    log_path = tmp_path / "requests.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_requests() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {"session_id": "s01", "feature": "qa", "message": "Explain monitoring"}
            return [
                await client.post("/chat", json={**payload, "user_id": "u01"},
                                  headers={"x-request-id": "req-abcdef12"}),
                await client.post("/chat", json={**payload, "user_id": "u02"},
                                  headers={"x-request-id": "malformed-header"}),
                await client.post("/chat", json={**payload, "user_id": "u03"}),
            ]

    responses = asyncio.run(send_requests())
    assert all(response.status_code == 200 for response in responses)
    ids = [response.headers["x-request-id"] for response in responses]
    assert ids[0] == "req-abcdef12"
    assert all(re.fullmatch(r"req-[0-9a-fA-F]{8}", request_id) for request_id in ids)
    assert len(set(ids)) == 3
    assert all(float(response.headers["x-response-time-ms"]) >= 0 for response in responses)
    records = [json.loads(line) for line in log_path.read_text().splitlines()]
    received = [record for record in records if record["event"] == "request_received"]
    assert [record["correlation_id"] for record in received] == ids
    assert len({record["user_id_hash"] for record in received}) == 3
    assert all(record["feature"] == "qa" and record["model"] for record in received)
    assert all(response.json()["correlation_id"] == request_id
               for response, request_id in zip(responses, ids))
