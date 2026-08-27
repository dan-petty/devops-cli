"""Tests for REST SSE and WebSocket agent reasoning streams."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from devops_cli.server.app import create_app


def test_streaming_sse_endpoint() -> None:
    """Verify /v1/stream/events endpoint registration and streaming response in FastAPI app."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/v1/stream/events")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


def test_websocket_reasoning_endpoint() -> None:
    """Verify /v1/ws/reasoning WebSocket streaming in FastAPI app."""
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/v1/ws/reasoning") as websocket:
        websocket.send_text(json.dumps({"persona": "devsecops"}))
        msg = websocket.receive_text()
        assert "event_type" in msg
