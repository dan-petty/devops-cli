"""Universal subprocess execution and SIEM audit pipeline for devops-cli."""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.telemetry import inject_trace_context, record_metric, trace_span


class ProcessExecutionResult(BaseModel):
    """Structured execution result from the universal process pipeline."""

    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    success: bool
    timeout_occurred: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessExecutionPipeline:
    """Centralized process execution runner with OTel tracing, timeouts, and audit logging."""

    def __init__(
        self,
        default_timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        cwd: Path | str | None = None,
    ) -> None:
        self.default_timeout = default_timeout
        self.cwd = Path(cwd) if cwd else Path.cwd()

    def run(
        self,
        command: Sequence[str | Path],
        *,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
        cwd: Path | str | None = None,
        check: bool = False,
        capture_output: bool = True,
        extra_attributes: dict[str, Any] | None = None,
    ) -> ProcessExecutionResult:
        """Execute a command list with bounded timeout, OTel tracing, and trace context propagation."""
        cmd_list = [str(c) for c in command]
        bin_name = Path(cmd_list[0]).name if cmd_list else "unknown"
        eff_timeout = timeout if timeout is not None else self.default_timeout
        eff_cwd = str(cwd or self.cwd)

        eff_env = dict(os.environ)
        if env:
            eff_env.update(env)

        # Inject W3C traceparent into subprocess environment
        trace_headers = inject_trace_context()
        if "traceparent" in trace_headers:
            eff_env["TRACEPARENT"] = trace_headers["traceparent"]

        t_start = time.perf_counter()
        span_attrs = {
            "process.executable.name": bin_name,
            "process.command": " ".join(cmd_list[:10]),
            "process.working_directory": eff_cwd,
            "process.timeout_seconds": eff_timeout,
        }
        if extra_attributes:
            span_attrs.update(extra_attributes)

        with trace_span("subprocess.exec", attributes=span_attrs) as span_h:
            span_h.add_event("process_started", {"binary": bin_name})
            timed_out = False
            stdout_str = ""
            stderr_str = ""
            ret_code = -1

            try:
                proc = subprocess.run(
                    cmd_list,
                    cwd=eff_cwd,
                    env=eff_env,
                    capture_output=capture_output,
                    text=True,
                    timeout=eff_timeout,
                    check=check,
                )
                ret_code = proc.returncode
                stdout_str = proc.stdout or ""
                stderr_str = proc.stderr or ""
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                ret_code = 124  # Standard timeout exit code
                stdout_str = (
                    exc.stdout.decode("utf-8", errors="replace")
                    if isinstance(exc.stdout, bytes)
                    else str(exc.stdout or "")
                )
                stderr_str = (
                    exc.stderr.decode("utf-8", errors="replace")
                    if isinstance(exc.stderr, bytes)
                    else str(exc.stderr or "")
                )
                span_h.record_exception(exc)
            except subprocess.CalledProcessError as exc:
                ret_code = exc.returncode
                stdout_str = exc.stdout or ""
                stderr_str = exc.stderr or ""
                span_h.record_exception(exc)
                if check:
                    raise

            elapsed = time.perf_counter() - t_start
            success = ret_code == 0 and not timed_out

            span_h.set_attribute("process.exit_code", ret_code)
            span_h.set_attribute("process.elapsed_seconds", elapsed)
            span_h.set_attribute("process.success", success)
            span_h.add_event(
                "process_completed",
                {"exit_code": ret_code, "elapsed_seconds": elapsed, "success": success},
            )

            record_metric(
                "subprocess.execution.duration_seconds",
                elapsed,
                attributes={"binary": bin_name, "success": success},
            )

            return ProcessExecutionResult(
                command=cmd_list,
                return_code=ret_code,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_seconds=elapsed,
                success=success,
                timeout_occurred=timed_out,
            )
