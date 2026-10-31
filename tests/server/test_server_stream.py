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


def test_streaming_sse_persona_validation() -> None:
    """Verify persona filtering and fallback to DEFAULT_STREAM_PERSONA."""
    from devops_cli.config.defaults import (
        DEFAULT_ALLOWED_STREAM_PERSONAS,
        DEFAULT_STREAM_PERSONA,
    )

    assert DEFAULT_STREAM_PERSONA in DEFAULT_ALLOWED_STREAM_PERSONAS
    assert "devsecops" in DEFAULT_ALLOWED_STREAM_PERSONAS

    app = create_app()
    client = TestClient(app)

    # Valid persona
    res_valid = client.get("/v1/stream/events?persona=architect")
    assert res_valid.status_code == 200
    assert "text/event-stream" in res_valid.headers.get("content-type", "")
    valid_data_lines = [
        line.removeprefix("data: ").strip()
        for line in res_valid.text.split("\n")
        if line.startswith("data: ")
    ]
    assert valid_data_lines
    assert json.loads(valid_data_lines[0])["persona"] == "architect"

    # Invalid persona falls back safely to DEFAULT_STREAM_PERSONA
    res_invalid = client.get("/v1/stream/events?persona=malicious_injected_persona")
    assert res_invalid.status_code == 200
    assert "text/event-stream" in res_invalid.headers.get("content-type", "")
    invalid_data_lines = [
        line.removeprefix("data: ").strip()
        for line in res_invalid.text.split("\n")
        if line.startswith("data: ")
    ]
    assert invalid_data_lines
    assert json.loads(invalid_data_lines[0])["persona"] == DEFAULT_STREAM_PERSONA


def test_websocket_invalid_persona_fallback() -> None:
    """Verify WebSocket fallback to DEFAULT_STREAM_PERSONA for invalid persona request."""
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/v1/ws/reasoning") as websocket:
        websocket.send_text(json.dumps({"persona": "unknown_invalid_persona"}))
        msg = websocket.receive_text()
        assert "event_type" in msg
        payload = json.loads(msg)
        assert payload["persona"] == "devsecops"
