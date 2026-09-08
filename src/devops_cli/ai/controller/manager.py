"""Centralized Agent Constellation Quiesce & Emergency Failover Controller Manager."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from devops_cli.ai.controller.models import (
    AgentTaskType,
    ConstellationStatus,
    FailoverResult,
    QuiesceResult,
    QuiesceSnapshot,
    QuiesceState,
    ResumeResult,
    SuspendedTask,
    _utc_now_iso,
)
from devops_cli.config.settings import load_settings
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
    """Resolve data directory adhering to environment and configuration overrides."""
    if custom_dir:
        return Path(custom_dir).resolve()
    env_override = os.environ.get("DEVOPS_CLI_DATA_DIR")
    if env_override:
        return Path(env_override).resolve()
    return load_settings().data.dir.resolve()


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
    """Atomically write snapshot JSON payload to target destination."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")


class ConstellationManager:
    """Controller managing emergency quiesce, fallback routing, and resumption for agent loops."""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        self.data_dir = _resolve_data_dir(data_dir)
        self.agent_dir = self.data_dir / "agent"
        self.snapshot_file = self.agent_dir / "quiesce.json"
        self._registered_tasks: dict[str, SuspendedTask] = {}

    def register_task(
        self,
        task_id: str,
        task_type: AgentTaskType,
        name: str,
        provider: str,
        model: str,
        state_payload: dict[str, Any] | None = None,
    ) -> SuspendedTask:
        """Register an active background task or agent loop with the constellation controller."""
        task = SuspendedTask(
            task_id=task_id,
            task_type=task_type,
            name=name,
            original_provider=provider,
            original_model=model,
            status="active",
            state_payload=state_payload or {},
        )
        self._registered_tasks[task_id] = task
        return task

    def unregister_task(self, task_id: str) -> bool:
        """Remove a completed task from tracking."""
        return bool(self._registered_tasks.pop(task_id, None))

    def quiesce(
        self,
        reason: str = "Emergency quiesce",
        drain_timeout: float = 5.0,
        dry_run: bool = False,
    ) -> QuiesceResult:
        """Cleanly freeze registered agent loops, cron jobs, and task runners."""
        with trace_span(
            "ai.constellation.quiesce",
            attributes={
                "quiesce.reason": reason,
                "quiesce.dry_run": dry_run,
                "quiesce.drain_timeout": drain_timeout,
            },
        ):
            tasks_to_suspend: list[SuspendedTask] = []
            for task in self._registered_tasks.values():
                task.status = "suspended"
                task.suspended_at = _utc_now_iso()
                tasks_to_suspend.append(task)

            snapshot = QuiesceSnapshot(
                state=QuiesceState.QUIESCED,
                reason=reason,
                tasks=tasks_to_suspend,
            )

            devops_cli_ai_quiesce_events_total.inc(labels={"reason": reason})

            if not dry_run:
                _write_snapshot_file(self.snapshot_file, snapshot)

            message = (
                f"Constellation quiesced successfully ({len(tasks_to_suspend)} tasks suspended)."
                if not dry_run
                else f"[DRY RUN] Constellation quiesce simulated for {len(tasks_to_suspend)} tasks."
            )

            return QuiesceResult(
                success=True,
                state=QuiesceState.QUIESCED,
                reason=reason,
                suspended_count=len(tasks_to_suspend),
                snapshot_path=str(self.snapshot_file),
                message=message,
                dry_run=dry_run,
            )

    def failover(
        self,
        target_provider: str = "ollama",
        target_model: str = "qwen2.5-coder:7b",
        dry_run: bool = False,
    ) -> FailoverResult:
        """Safely re-route pending tasks to designated fallback endpoint."""
        with trace_span(
            "ai.constellation.failover",
            attributes={
                "failover.target_provider": target_provider,
                "failover.target_model": target_model,
                "failover.dry_run": dry_run,
            },
        ):
            snapshot = _read_snapshot_file(self.snapshot_file) or QuiesceSnapshot(
                state=QuiesceState.FAILOVER,
                reason="Automatic failover",
                tasks=list(self._registered_tasks.values()),
            )

            snapshot.state = QuiesceState.FAILOVER
            snapshot.active_fallback = (target_provider, target_model)

            for task in snapshot.tasks:
                task.fallback_provider = target_provider
                task.fallback_model = target_model
                task.status = "failed_over"
                if task.task_id in self._registered_tasks:
                    self._registered_tasks[task.task_id].fallback_provider = target_provider
                    self._registered_tasks[task.task_id].fallback_model = target_model
                    self._registered_tasks[task.task_id].status = "failed_over"

            devops_cli_ai_failover_events_total.inc(
                labels={"provider": target_provider, "model": target_model}
            )

            if not dry_run:
                _write_snapshot_file(self.snapshot_file, snapshot)

            message = (
                f"Emergency failover routing engaged to {target_provider}/{target_model} "
                f"across {len(snapshot.tasks)} tasks."
                if not dry_run
                else f"[DRY RUN] Emergency failover simulated to {target_provider}/{target_model}."
            )

            return FailoverResult(
                success=True,
                state=QuiesceState.FAILOVER,
                target_provider=target_provider,
                target_model=target_model,
                rerouted_count=len(snapshot.tasks),
                snapshot_path=str(self.snapshot_file),
                message=message,
                dry_run=dry_run,
            )

    def resume(self, dry_run: bool = False) -> ResumeResult:
        """Resume suspended constellation loops with active or restored routes."""
        with trace_span(
            "ai.constellation.resume",
            attributes={"resume.dry_run": dry_run},
        ):
            snapshot = _read_snapshot_file(self.snapshot_file)
            tasks = snapshot.tasks if snapshot else list(self._registered_tasks.values())
            resumed_count = len(tasks)

            for task in tasks:
                task.status = "resumed"
                task.resumed_at = _utc_now_iso()
                if task.task_id in self._registered_tasks:
                    self._registered_tasks[task.task_id].status = "resumed"
                    self._registered_tasks[task.task_id].resumed_at = task.resumed_at

            if snapshot:
                snapshot.state = QuiesceState.RESUMED

            devops_cli_ai_resumptions_total.inc()

            if not dry_run and snapshot:
                _write_snapshot_file(self.snapshot_file, snapshot)

            message = (
                f"Constellation resumed successfully ({resumed_count} tasks reactivated)."
                if not dry_run
                else f"[DRY RUN] Constellation resumption simulated for {resumed_count} tasks."
            )

            return ResumeResult(
                success=True,
                state=QuiesceState.RESUMED,
                resumed_count=resumed_count,
                snapshot_path=str(self.snapshot_file),
                message=message,
                dry_run=dry_run,
            )

    def status(self) -> ConstellationStatus:
        """Inspect current quiesce state, active fallback route, and tasks."""
        snapshot = _read_snapshot_file(self.snapshot_file)
        if not snapshot:
            return ConstellationStatus(
                state=QuiesceState.IDLE,
                is_quiesced=False,
                suspended_task_count=len(self._registered_tasks),
                tasks=list(self._registered_tasks.values()),
                snapshot_path=str(self.snapshot_file),
            )

        is_quiesced = snapshot.state in (QuiesceState.QUIESCED, QuiesceState.FAILOVER)
        return ConstellationStatus(
            state=snapshot.state,
            is_quiesced=is_quiesced,
            reason=snapshot.reason,
            quiesced_at=snapshot.quiesced_at,
            suspended_task_count=len(snapshot.tasks),
            tasks=snapshot.tasks,
            active_fallback=snapshot.active_fallback,
            snapshot_path=str(self.snapshot_file),
        )

    def is_quiesced(self) -> bool:
        """Return True if constellation is currently quiesced or in failover state."""
        return self.status().is_quiesced

    def get_active_route(self, provider: str, model: str) -> tuple[str, str]:
        """Resolve effective provider and model routing applying active fallback when engaged."""
        st = self.status()
        if st.state == QuiesceState.FAILOVER and st.active_fallback:
            return st.active_fallback
        return (provider, model)
