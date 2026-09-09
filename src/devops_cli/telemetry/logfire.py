"""Native Pydantic Logfire structured AI observability bridge for devops-cli."""

from __future__ import annotations

import contextlib
import logging
import os
import threading
import time
from collections.abc import Generator
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.settings import Settings, get_logfire_token, load_settings
from devops_cli.exceptions.telemetry import LogfireConfigurationError
from devops_cli.output import Panel, Table
from devops_cli.telemetry.tracer import _to_otlp_any_value, record_completed_span

logger = logging.getLogger(__name__)

_GLOBAL_LOGFIRE_BRIDGE: LogfireBridge | None = None
_BRIDGE_LOCK = threading.Lock()


class LogfireStatus(BaseModel):
    """Status model reporting active Logfire bridge state and token metrics."""

    enabled: bool = False
    token_configured: bool = False
    send_to_logfire: bool | str = "if-token-present"
    active_spans_count: int = 0
    token_metrics: dict[str, int] = Field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    )
    turns_count: int = 0


class LogfireOTelBridgeProcessor:
    """OpenTelemetry SpanProcessor that bridges finished Logfire spans to internal tracer records."""

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        """No-op start handler for OpenTelemetry SpanProcessor contract."""

    def on_end(self, span: Any) -> None:
        """Process completed span and record to internal completed spans buffer."""
        try:
            ctx = getattr(span, "context", None)
            if not ctx:
                return
            trace_id_val = getattr(ctx, "trace_id", None)
            span_id_val = getattr(ctx, "span_id", None)
            if not trace_id_val or not span_id_val:
                return

            trace_id_hex = format(int(trace_id_val), "032x")
            span_id_hex = format(int(span_id_val), "016x")
            parent_id_hex = None
            parent = getattr(span, "parent", None)
            if parent and hasattr(parent, "span_id") and parent.span_id:
                parent_id_hex = format(int(parent.span_id), "016x")

            status_obj = getattr(span, "status", None)
            status_code = "STATUS_CODE_UNSET"
            if status_obj:
                code_attr = getattr(status_obj, "status_code", None)
                status_code = getattr(code_attr, "name", str(code_attr))

            raw_attrs = dict(getattr(span, "attributes", {}) or {})
            otlp_attrs = [
                {"key": str(k), "value": _to_otlp_any_value(v)} for k, v in raw_attrs.items()
            ]

            record = {
                "name": getattr(span, "name", "logfire.span"),
                "spanId": span_id_hex,
                "traceId": trace_id_hex,
                "parentSpanId": parent_id_hex,
                "startTimeUnixNano": str(getattr(span, "start_time", 0)),
                "endTimeUnixNano": str(getattr(span, "end_time", 0)),
                "attributes": otlp_attrs,
                "status": {"code": status_code},
            }
            record_completed_span(record)
        except Exception as exc:
            logger.debug("Failed to bridge Logfire span to internal tracer: %s", exc)

    def shutdown(self) -> None:
        """No-op shutdown handler."""

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """No-op flush handler."""
        return True


class AgentTurnHandle:
    """Handle for recording telemetry, response content, and tokens for an agent turn."""

    def __init__(
        self,
        agent_name: str,
        turn_index: int,
        prompt: str | None = None,
        model: str | None = None,
        span_handle: Any = None,
    ) -> None:
        self.agent_name = agent_name
        self.turn_index = turn_index
        self.prompt = prompt or ""
        self.model = model or ""
        self.response = ""
        self.tools_called: list[str] = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.start_time = time.perf_counter()
        self.duration_ms = 0.0
        self._span_handle = span_handle

    def set_response(self, response: str) -> None:
        """Record agent response preview."""
        self.response = response
        if self._span_handle and hasattr(self._span_handle, "set_attribute"):
            self._span_handle.set_attribute("agent.response", response[:500])

    def record_tokens(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Record token usage for this turn."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens

        bridge = get_logfire_bridge()
        bridge.accumulate_tokens(input_tokens, output_tokens)

        try:
            import logfire

            logfire.metric_counter("agent.tokens.input").add(input_tokens)
            logfire.metric_counter("agent.tokens.output").add(output_tokens)
            logfire.metric_counter("agent.tokens.total").add(input_tokens + output_tokens)
        except Exception as exc:
            logger.debug("Logfire token metric counter update suppressed: %s", exc)

    def record_tool_call(
        self, tool_name: str, args: dict[str, Any] | None = None, result: Any = None
    ) -> None:
        """Record tool invocation details."""
        self.tools_called.append(tool_name)
        if self._span_handle and hasattr(self._span_handle, "set_attribute"):
            self._span_handle.set_attribute(
                f"agent.tools.{len(self.tools_called)}",
                f"{tool_name}({list((args or {}).keys())})",
            )

    def finalize(self) -> None:
        """Compute duration and record turn completion metric."""
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000
        try:
            import logfire

            logfire.metric_counter("agent.turns.total").add(1)
        except Exception as exc:
            logger.debug("Logfire turn counter metric suppressed: %s", exc)


class LogfireBridge:
    """Manages configuration, secret resolution, instrumentation, and metrics for Logfire."""

    def __init__(self) -> None:
        self._enabled: bool = False
        self._token_configured: bool = False
        self._send_to_logfire: bool | str = "if-token-present"
        self._token_metrics: dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
        self._turns_count: int = 0
        self._lock = threading.Lock()

    def configure(
        self,
        settings: Settings | None = None,
        token: str | None = None,
        send_to_logfire: bool | str | None = None,
        console: bool = False,
    ) -> None:
        """Configure and activate the Logfire bridge with graceful fallback."""
        active_settings = settings or load_settings()
        resolved_token = token or get_logfire_token(active_settings) or os.getenv("LOGFIRE_TOKEN")
        self._token_configured = bool(resolved_token)

        if send_to_logfire is not None:
            effective_send = send_to_logfire
        elif resolved_token:
            effective_send = True
        else:
            effective_send = False

        self._send_to_logfire = effective_send

        try:
            import logfire

            processor = LogfireOTelBridgeProcessor()
            logfire.configure(
                send_to_logfire=effective_send,  # type: ignore[arg-type]
                token=resolved_token,
                console=None if console else False,
                additional_span_processors=[processor],  # type: ignore[list-item]
                inspect_arguments=False,
            )

            with contextlib.suppress(Exception):
                logfire.instrument_pydantic()
            with contextlib.suppress(Exception):
                logfire.instrument_pydantic_ai()

            self._enabled = True
        except Exception as exc:
            logger.warning("Failed to configure Logfire bridge: %s", exc)
            self._enabled = False
            raise LogfireConfigurationError(f"Failed to configure Logfire bridge: {exc}") from exc

    def is_active(self) -> bool:
        """Return True if Logfire is configured and active."""
        return self._enabled

    def accumulate_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Accumulate token counts across agent runs."""
        with self._lock:
            self._token_metrics["input_tokens"] += input_tokens
            self._token_metrics["output_tokens"] += output_tokens
            self._token_metrics["total_tokens"] += input_tokens + output_tokens

    def increment_turns(self) -> None:
        """Increment recorded turn counter."""
        with self._lock:
            self._turns_count += 1

    def flush(self) -> None:
        """Flush pending Logfire spans."""
        if not self._enabled:
            return
        try:
            import logfire

            logfire.force_flush()
        except Exception as exc:
            logger.debug("Logfire flush error suppressed: %s", exc)

    def shutdown(self) -> None:
        """Shut down Logfire runtime."""
        if not self._enabled:
            return
        try:
            import logfire

            logfire.shutdown()
        except Exception as exc:
            logger.debug("Logfire shutdown error suppressed: %s", exc)
        finally:
            self._enabled = False

    def get_status(self) -> LogfireStatus:
        """Return current status of the Logfire bridge."""
        from devops_cli.telemetry.tracer import get_recent_spans

        active_spans = len(get_recent_spans())
        with self._lock:
            return LogfireStatus(
                enabled=self._enabled,
                token_configured=self._token_configured,
                send_to_logfire=self._send_to_logfire,
                active_spans_count=active_spans,
                token_metrics=dict(self._token_metrics),
                turns_count=self._turns_count,
            )


def get_logfire_bridge() -> LogfireBridge:
    """Retrieve or initialize the global LogfireBridge instance."""
    global _GLOBAL_LOGFIRE_BRIDGE
    with _BRIDGE_LOCK:
        if _GLOBAL_LOGFIRE_BRIDGE is None:
            _GLOBAL_LOGFIRE_BRIDGE = LogfireBridge()
        return _GLOBAL_LOGFIRE_BRIDGE


def reset_logfire_bridge() -> None:
    """Reset the global LogfireBridge instance (used for testing)."""
    global _GLOBAL_LOGFIRE_BRIDGE
    with _BRIDGE_LOCK:
        if _GLOBAL_LOGFIRE_BRIDGE is not None:
            _GLOBAL_LOGFIRE_BRIDGE.shutdown()
        _GLOBAL_LOGFIRE_BRIDGE = None


@contextlib.contextmanager
def logfire_agent_turn(
    agent_name: str,
    turn_index: int,
    prompt: str | None = None,
    model: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Generator[AgentTurnHandle]:
    """Context manager for tracing an agent turn with Logfire structured observability."""
    bridge = get_logfire_bridge()
    bridge.increment_turns()

    span_attrs: dict[str, Any] = {
        "agent.name": agent_name,
        "agent.turn_index": turn_index,
        "agent.prompt": (prompt or "")[:500],
        "agent.model": model or "unknown",
    }
    if attributes:
        span_attrs.update(attributes)

    span_cm: Any
    try:
        import logfire

        span_cm = logfire.span(f"agent.turn.{agent_name}", **span_attrs)
    except Exception:
        span_cm = contextlib.nullcontext()

    with span_cm as span_ctx:
        handle = AgentTurnHandle(
            agent_name=agent_name,
            turn_index=turn_index,
            prompt=prompt,
            model=model,
            span_handle=span_ctx,
        )
        try:
            yield handle
        finally:
            handle.finalize()


def render_agent_turn_table(turn_info: dict[str, Any]) -> Table:
    """Render Rich table formatting an agent turn's structured telemetry."""
    table = Table(
        title=f"Agent Turn: {turn_info.get('agent_name', 'agent')} (Turn {turn_info.get('turn_index', 1)})",
        border_style="cyan",
    )
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Agent", str(turn_info.get("agent_name", "unknown")))
    table.add_row("Turn Index", str(turn_info.get("turn_index", 1)))
    prompt_val = str(turn_info.get("prompt", ""))
    table.add_row("Prompt Preview", prompt_val[:100] + ("..." if len(prompt_val) > 100 else ""))
    resp_val = str(turn_info.get("response", ""))
    table.add_row("Response Preview", resp_val[:100] + ("..." if len(resp_val) > 100 else ""))

    tools = turn_info.get("tools_called", [])
    table.add_row("Tools Called", ", ".join(tools) if tools else "None")

    usage = turn_info.get("token_usage", {})
    in_tok = usage.get("input_tokens", 0)
    out_tok = usage.get("output_tokens", 0)
    tot_tok = usage.get("total_tokens", in_tok + out_tok)
    table.add_row("Token Usage", f"In: {in_tok} | Out: {out_tok} | Total: {tot_tok}")

    if "duration_ms" in turn_info:
        table.add_row("Duration", f"{turn_info['duration_ms']:.2f} ms")

    return table


def render_agent_turn_panel(turn_info: dict[str, Any]) -> Panel:
    """Render Rich panel wrapping an agent turn's structured telemetry table."""
    table = render_agent_turn_table(turn_info)
    return Panel(
        table,
        title="[bold blue]Logfire Agent Observability[/bold blue]",
        border_style="bright_blue",
    )
