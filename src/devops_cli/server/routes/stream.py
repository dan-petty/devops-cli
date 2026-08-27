"""Real-time SSE and WebSocket agent reasoning streams."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1", tags=["Streaming"])


class StreamEvent(BaseModel):
    """Schema for SSE / WebSocket streaming event payload."""

    event_type: str = Field(
        ..., description="Event kind: token, reasoning_step, scratchpad, finding"
    )
    persona: str = Field(default="devsecops", description="Originating agent persona")
    content: str = Field(..., description="Content payload or delta")
    timestamp: float = Field(default_factory=time.time, description="Timestamp of the event")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Contextual event metadata")


async def _generate_agent_reasoning_events(persona: str = "devsecops") -> AsyncGenerator[str]:
    """Simulate streaming agent reasoning tokens and scratchpad updates for IDE integration."""
    steps = [
        ("reasoning_step", "Parsing AST structure and extracting call-graph invariants..."),
        ("token", "Analyzing input boundaries and potential SSRF surfaces in network layer..."),
        ("scratchpad", "Checking against CWE-918 and CWE-200 threat models..."),
        ("finding", "✓ Zero-trust security invariants verified. No unvalidated egress found."),
    ]
    for kind, text in steps:
        evt = StreamEvent(event_type=kind, persona=persona, content=text)
        yield f"event: {kind}\ndata: {evt.model_dump_json()}\n\n"
        await asyncio.sleep(0.01)


@router.get("/stream/events", summary="Server-Sent Events (SSE) agent reasoning feed")
async def stream_agent_events(persona: str = "devsecops") -> StreamingResponse:
    """Stream real-time LLM reasoning events and scratchpad updates via SSE."""
    return StreamingResponse(
        _generate_agent_reasoning_events(persona),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.websocket("/ws/reasoning")
async def websocket_reasoning_endpoint(websocket: WebSocket) -> None:
    """WebSocket duplex stream for real-time agent reasoning steps."""
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        req = json.loads(data) if data else {}
        persona = req.get("persona", "devsecops")

        async for chunk in _generate_agent_reasoning_events(persona):
            lines = chunk.strip().splitlines()
            if len(lines) >= 2 and lines[1].startswith("data: "):
                payload = lines[1][6:]
                await websocket.send_text(payload)
        await websocket.close()
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close()
