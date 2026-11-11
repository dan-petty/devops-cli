"""Native Pydantic Logfire structured AI observability bridge for devops-cli."""

from __future__ import annotations

import contextlib
import logging
import os
import threading
from typing import Any

from pydantic import BaseModel

from devops_cli.config.settings import Settings, get_logfire_token, load_settings
from devops_cli.exceptions.telemetry import LogfireConfigurationError
from devops_cli.security.sanitizer import PRIVATE_HOST_PATTERNS
from devops_cli.telemetry.tracer import _to_otlp_any_value, record_completed_span

logger = logging.getLogger(__name__)

_GLOBAL_LOGFIRE_BRIDGE: LogfireBridge | None = None
_BRIDGE_LOCK = threading.Lock()


class LogfireStatus(BaseModel):
    """Status model reporting the state of the Logfire bridge."""

    enabled: bool = False
    token_configured: bool = False
    send_to_logfire: bool | str = "if-token-present"
    active_spans_count: int = 0


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


class LogfireBridge:
    """Manages configuration, secret resolution, instrumentation, and metrics for Logfire."""

    def __init__(self) -> None:
        self._enabled: bool = False
        self._token_configured: bool = False
        self._send_to_logfire: bool | str = "if-token-present"

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

            from devops_cli.telemetry.library_spans import library_span_processor

            # The cluster collector gets the agent spans too, through the exporter seam.
            seam = library_span_processor()
            processors = [LogfireOTelBridgeProcessor(), *([seam] if seam is not None else [])]
            logfire.configure(
                send_to_logfire=effective_send,  # type: ignore[arg-type]
                token=resolved_token,
                console=None if console else False,
                additional_span_processors=processors,  # type: ignore[arg-type]
                inspect_arguments=False,
                scrubbing=logfire.ScrubbingOptions(extra_patterns=PRIVATE_HOST_PATTERNS),
            )

            capture_llm_content = getattr(
                getattr(active_settings, "telemetry", None), "capture_llm_content", False
            )
            with contextlib.suppress(Exception):
                logfire.instrument_pydantic_ai(include_content=capture_llm_content)

            self._enabled = True
        except Exception as exc:
            logger.warning("Failed to configure Logfire bridge: %s", exc)
            self._enabled = False
            raise LogfireConfigurationError(f"Failed to configure Logfire bridge: {exc}") from exc

    def is_active(self) -> bool:
        """Return True if Logfire is configured and active."""
        return self._enabled

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

        return LogfireStatus(
            enabled=self._enabled,
            token_configured=self._token_configured,
            send_to_logfire=self._send_to_logfire,
            active_spans_count=len(get_recent_spans()),
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
