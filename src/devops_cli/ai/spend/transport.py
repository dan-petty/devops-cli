"""Transport wrapper between egress and retry that records failed attempts to the spend ledger."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx2

from devops_cli.ai.client.network import (
    active_dispatch_context,
    extract_served_by,
    extract_served_model,
)
from devops_cli.config.constants import CONST_FINISH_REASON_ERROR

logger = logging.getLogger(__name__)


def record_failed_attempt(
    *,
    request: httpx2.Request,
    duration: float,
    headers: Any = None,
    response: httpx2.Response | None = None,
) -> None:
    """Record one failed attempt of the active dispatch in the spend ledger, with finish reason
    `error`. When no dispatch is active, record nothing.

    The transport records an attempt that fails inside it. A chat call records an attempt whose
    stream fails after the transport returned its status line (#2365), with no `response`, as
    the stream has been read.
    """
    ctx = active_dispatch_context.get()
    if ctx is None:
        return

    from devops_cli.ai.spend import resolve_spend_stage, track_request_spend

    served_by = extract_served_by(headers)
    served_model = extract_served_model(headers)
    prompt_tokens = 0
    completion_tokens = 0

    if response is not None:
        try:
            try:
                response.read()
            except (httpx2.HTTPError, RuntimeError) as exc:
                logger.debug("Failed reading response content: %s", exc)
            data = response.json()
            if isinstance(data, dict):
                usage = data.get("usage")
                if isinstance(usage, dict):
                    prompt_tokens = int(usage.get("prompt_tokens") or 0)
                    completion_tokens = int(usage.get("completion_tokens") or 0)
                if not served_model:
                    err_obj = data.get("error")
                    err_dict = err_obj if isinstance(err_obj, dict) else {}
                    m = data.get("model") or err_dict.get("model")
                    if m and m != ctx.model:
                        served_model = str(m)
        except (ValueError, UnicodeDecodeError, httpx2.HTTPError, RuntimeError) as exc:
            logger.debug("Failed to parse response JSON: %s", exc)

    track_request_spend(
        provider=ctx.provider,
        model=ctx.model,
        server=ctx.server or request.url.netloc.decode("ascii", errors="replace"),
        backend_info=ctx.backend_info,
        served_by=served_by,
        served_model=served_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached=False,
        request_type=ctx.request_type,
        duration_seconds=duration,
        stage=resolve_spend_stage(None, ctx.task_name),
        finish_reason=CONST_FINISH_REASON_ERROR,
    )


class AttemptRecordingTransport(httpx2.BaseTransport):
    """Transport wrapper between egress and retry that records failed attempts to the spend ledger."""

    def __init__(self, wrapped: httpx2.BaseTransport) -> None:
        self.wrapped = wrapped

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        ctx = active_dispatch_context.get()
        if ctx is None:
            return self.wrapped.handle_request(request)

        t_start = time.perf_counter()
        try:
            response = self.wrapped.handle_request(request)
        except httpx2.ConnectError, httpx2.ConnectTimeout:
            raise
        except (httpx2.ReadTimeout, httpx2.HTTPError) as exc:
            duration = time.perf_counter() - t_start
            resp = getattr(exc, "response", None)
            record_failed_attempt(
                request=request,
                duration=duration,
                headers=getattr(resp, "headers", None),
                response=resp,
            )
            raise

        if response.status_code >= 400:
            duration = time.perf_counter() - t_start
            record_failed_attempt(
                request=request,
                duration=duration,
                headers=response.headers,
                response=response,
            )
        return response

    def __enter__(self) -> AttemptRecordingTransport:
        self.wrapped.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: Any = None,
    ) -> None:
        self.wrapped.__exit__(exc_type, exc_value, traceback)

    def close(self) -> None:
        self.wrapped.close()


__all__ = ["AttemptRecordingTransport", "record_failed_attempt"]
