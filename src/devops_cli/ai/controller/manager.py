"""Centralized Agent Constellation Quiesce & Emergency Failover Controller Manager."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from devops_cli.ai.controller.models import (
    ConstellationStatus,
    FailoverResult,
    QuiesceResult,
    QuiesceSnapshot,
    QuiesceState,
    ResumeResult,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_FALLBACK_MODEL,
    DEFAULT_AI_FALLBACK_PROVIDER,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.paths import is_forbidden_system_path
from devops_cli.core.repo import resolve_data_path
from devops_cli.exceptions.security import SecurityError
from devops_cli.lang import MESSAGES
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import trace_span

logger = logging.getLogger(__name__)

_METRIC_QUIESCE_EVENTS = "devops_cli_ai_quiesce_events_total"
_METRIC_FAILOVER_EVENTS = "devops_cli_ai_failover_events_total"
_METRIC_RESUME_EVENTS = "devops_cli_ai_resumptions_total"


class _MetricCounterStub:
    """Wrapper exposing Prometheus counter interface backed by GLOBAL_METRICS."""

    def __init__(self, metric_name: str) -> None:
        self.metric_name = metric_name

    def inc(self, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment Prometheus counter."""
        GLOBAL_METRICS.increment_counter(self.metric_name, value=amount, labels=labels or {})


devops_cli_ai_quiesce_events_total = _MetricCounterStub(_METRIC_QUIESCE_EVENTS)
devops_cli_ai_failover_events_total = _MetricCounterStub(_METRIC_FAILOVER_EVENTS)
devops_cli_ai_resumptions_total = _MetricCounterStub(_METRIC_RESUME_EVENTS)


def _resolve_data_dir(custom_dir: Path | str | None = None) -> Path:
    """Resolve data directory adhering to environment and configuration overrides; a relative
    configured one is under the main worktree, shared by every worktree."""
    if custom_dir:
        candidate = Path(custom_dir).resolve()
    elif env_override := os.environ.get("DEVOPS_CLI_DATA_DIR"):
        candidate = resolve_data_path(Path(env_override)).resolve()
    else:
        candidate = resolve_data_path(load_settings().data.dir).resolve()

    if is_forbidden_system_path(candidate):
        raise SecurityError(
            f"Data directory cannot be located in forbidden system path: '{candidate}'."
        )
    return candidate


def _read_snapshot_file(file_path: Path) -> QuiesceSnapshot | None:
    """Safely load and validate snapshot JSON from disk, handling malformed content."""
    if not file_path.is_file():
        return None
    try:
        raw_text = file_path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
        return QuiesceSnapshot.model_validate(data)
    except Exception as exc:
        logger.warning("Failed reading quiesce snapshot at '%s': %s", file_path, exc)
        return None


def _write_snapshot_file(file_path: Path, snapshot: QuiesceSnapshot) -> None:
    """Atomically write snapshot JSON payload to target destination using tempfile and os.replace."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=file_path.parent,
            delete=False,
            prefix="quiesce_",
            suffix=".tmp",
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(snapshot.model_dump_json(indent=2))
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, file_path)
    except Exception:
        if tmp_path and tmp_path.is_file():
            tmp_path.unlink(missing_ok=True)
        raise


class ConstellationManager:
    """Set, record and clear the constellation flag in the data directory.

    The flag records an operator's intent to quiesce or fail over; no running task reads it,
    and requests are rerouted by `devops ai gateway failover`.
    """

    def __init__(self, data_dir: Path | str | None = None) -> None:
        self.data_dir = _resolve_data_dir(data_dir)
        self.agent_dir = self.data_dir / "agent"
        self.snapshot_file = self.agent_dir / "quiesce.json"

    def quiesce(
        self,
        reason: str = MESSAGES.ai.default_quiesce_reason,
        dry_run: bool = False,
    ) -> QuiesceResult:
        """Set the quiesce flag with a reason."""
        with trace_span(
            "ai.constellation.quiesce",
            attributes={"quiesce.reason": reason, "quiesce.dry_run": dry_run},
        ):
            snapshot = QuiesceSnapshot(state=QuiesceState.QUIESCED, reason=reason)
            devops_cli_ai_quiesce_events_total.inc()
            if not dry_run:
                _write_snapshot_file(self.snapshot_file, snapshot)
            return QuiesceResult(
                success=True,
                state=QuiesceState.QUIESCED,
                reason=reason,
                snapshot_path=str(self.snapshot_file),
                message=(
                    "[DRY RUN] Quiesce flag not written."
                    if dry_run
                    else "Quiesce flag set. No running task reads it."
                ),
                dry_run=dry_run,
            )

    def failover(
        self,
        target_provider: str = DEFAULT_AI_FALLBACK_PROVIDER,
        target_model: str = DEFAULT_AI_FALLBACK_MODEL,
        dry_run: bool = False,
    ) -> FailoverResult:
        """Record a fallback route in the flag."""
        with trace_span(
            "ai.constellation.failover",
            attributes={
                "failover.target_provider": target_provider,
                "failover.target_model": target_model,
                "failover.dry_run": dry_run,
            },
        ):
            snapshot = _read_snapshot_file(self.snapshot_file) or QuiesceSnapshot(reason="Failover")
            snapshot.state = QuiesceState.FAILOVER
            snapshot.active_fallback = (target_provider, target_model)
            devops_cli_ai_failover_events_total.inc(
                labels={"provider": target_provider, "model": target_model}
            )
            if not dry_run:
                _write_snapshot_file(self.snapshot_file, snapshot)
            return FailoverResult(
                success=True,
                state=QuiesceState.FAILOVER,
                target_provider=target_provider,
                target_model=target_model,
                snapshot_path=str(self.snapshot_file),
                message=(
                    "[DRY RUN] Failover flag not written."
                    if dry_run
                    else (
                        f"Fallback {target_provider}/{target_model} recorded in the flag; "
                        "`devops ai gateway failover` reroutes requests."
                    )
                ),
                dry_run=dry_run,
            )

    def resume(self, dry_run: bool = False) -> ResumeResult:
        """Clear the quiesce or failover flag."""
        with trace_span("ai.constellation.resume", attributes={"resume.dry_run": dry_run}):
            snapshot = _read_snapshot_file(self.snapshot_file)
            devops_cli_ai_resumptions_total.inc()
            if snapshot is not None and not dry_run:
                snapshot.state = QuiesceState.RESUMED
                snapshot.active_fallback = None
                _write_snapshot_file(self.snapshot_file, snapshot)
            if dry_run:
                message = "[DRY RUN] Flag not cleared."
            elif snapshot is None:
                message = "No quiesce or failover flag was set."
            else:
                message = "Quiesce and failover flag cleared."
            return ResumeResult(
                success=True,
                state=QuiesceState.RESUMED,
                snapshot_path=str(self.snapshot_file),
                message=message,
                dry_run=dry_run,
            )

    def status(self) -> ConstellationStatus:
        """Read the flag as last set."""
        snapshot = _read_snapshot_file(self.snapshot_file)
        if not snapshot:
            return ConstellationStatus(
                state=QuiesceState.IDLE,
                is_quiesced=False,
                snapshot_path=str(self.snapshot_file),
            )
        return ConstellationStatus(
            state=snapshot.state,
            is_quiesced=snapshot.state in (QuiesceState.QUIESCED, QuiesceState.FAILOVER),
            reason=snapshot.reason,
            quiesced_at=snapshot.quiesced_at,
            active_fallback=snapshot.active_fallback,
            snapshot_path=str(self.snapshot_file),
        )
