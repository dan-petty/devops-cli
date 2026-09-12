"""Unit and integration test suite for Agent Constellation Quiesce & Emergency Failover Controller."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.controller.manager import ConstellationManager
from devops_cli.ai.controller.models import (
    AgentTaskType,
    ConstellationStatus,
    FailoverResult,
    QuiesceResult,
    QuiesceSnapshot,
    QuiesceState,
    ResumeResult,
    SuspendedTask,
)
from devops_cli.exceptions.ai import (
    ConstellationFailoverError,
    ConstellationQuiesceError,
    ConstellationResumeError,
)
from devops_cli.main import app

runner = CliRunner()


class TestConstellationModels:
    """Test domain models, enums, and serialization for constellation controller."""

    def test_enum_values(self) -> None:
        """Verify enum constants match expected values."""
        assert QuiesceState.IDLE.value == "idle"
        assert QuiesceState.QUIESCED.value == "quiesced"
        assert QuiesceState.FAILOVER.value == "failover"
        assert QuiesceState.RESUMED.value == "resumed"

        assert AgentTaskType.REVIEW_LOOP.value == "review_loop"
        assert AgentTaskType.CRON_JOB.value == "cron_job"
        assert AgentTaskType.FILE_WATCHER.value == "file_watcher"
        assert AgentTaskType.SLOT_WORKER.value == "slot_worker"
        assert AgentTaskType.SUBAGENT.value == "subagent"
        assert AgentTaskType.BENCHMARK.value == "benchmark"

    def test_suspended_task_model(self) -> None:
        """Verify SuspendedTask serialization and defaults."""
        task = SuspendedTask(
            task_id="task-123",
            task_type=AgentTaskType.REVIEW_LOOP,
            name="pr-code-review-worker",
            original_provider="openai",
            original_model="gpt-4o",
            state_payload={"pending_files": ["main.py", "auth.py"]},
        )
        data = task.model_dump()
        assert data["task_id"] == "task-123"
        assert data["task_type"] == "review_loop"
        assert data["original_provider"] == "openai"
        assert data["original_model"] == "gpt-4o"
        assert data["status"] == "suspended"
        assert data["state_payload"]["pending_files"] == ["main.py", "auth.py"]

    def test_quiesce_snapshot_model(self) -> None:
        """Verify QuiesceSnapshot model structure and defaults."""
        snapshot = QuiesceSnapshot(
            snapshot_id="snap-001",
            state=QuiesceState.QUIESCED,
            reason="Upstream rate limit outage",
            quiesced_at="2026-09-08T12:00:00Z",
            tasks=[
                SuspendedTask(
                    task_id="t1",
                    task_type=AgentTaskType.CRON_JOB,
                    name="nightly-eval",
                    original_provider="anthropic",
                    original_model="claude-3-7-sonnet",
                )
            ],
            active_fallback=("ollama", "qwen2.5-coder:7b"),
        )
        assert snapshot.snapshot_id == "snap-001"
        assert snapshot.state == QuiesceState.QUIESCED
        assert len(snapshot.tasks) == 1
        assert snapshot.active_fallback == ("ollama", "qwen2.5-coder:7b")

    def test_result_models(self) -> None:
        """Verify QuiesceResult, FailoverResult, ResumeResult, and ConstellationStatus models."""
        q_res = QuiesceResult(
            success=True,
            state=QuiesceState.QUIESCED,
            reason="testing",
            suspended_count=1,
            snapshot_path="/tmp/snap.json",
            message="Quiesced",
        )
        assert q_res.success is True
        assert q_res.suspended_count == 1

        f_res = FailoverResult(
            success=True,
            state=QuiesceState.FAILOVER,
            target_provider="ollama",
            target_model="qwen2.5-coder:7b",
            rerouted_count=1,
            snapshot_path="/tmp/snap.json",
            message="Failover",
        )
        assert f_res.target_provider == "ollama"

        r_res = ResumeResult(
            success=True,
            state=QuiesceState.RESUMED,
            resumed_count=1,
            snapshot_path="/tmp/snap.json",
            message="Resumed",
        )
        assert r_res.resumed_count == 1

        status = ConstellationStatus(
            state=QuiesceState.IDLE,
            is_quiesced=False,
            reason="idle",
        )
        assert status.state == QuiesceState.IDLE

    def test_domain_exceptions(self) -> None:
        """Verify strongly typed domain exceptions for constellation subsystem."""
        q_err = ConstellationQuiesceError("Failed quiescing", reason="timeout")
        assert "Failed quiescing" in str(q_err)
        assert q_err.details["reason"] == "timeout"

        f_err = ConstellationFailoverError(
            "Failed failover", target_provider="ollama", target_model="qwen"
        )
        assert f_err.details["target_provider"] == "ollama"

        r_err = ConstellationResumeError("Failed resuming")
        assert "Failed resuming" in str(r_err)


class TestConstellationManager:
    """Test ConstellationManager controller behavior and state persistence."""

    @pytest.fixture
    def test_data_dir(self, tmp_path: Path) -> Path:
        """Provide isolated data directory."""
        return tmp_path / ".data"

    @pytest.fixture
    def manager(self, test_data_dir: Path) -> ConstellationManager:
        """Instantiate ConstellationManager with isolated directory."""
        return ConstellationManager(data_dir=test_data_dir)

    def test_initial_status_idle(self, manager: ConstellationManager) -> None:
        """Verify controller starts in IDLE state with no snapshot."""
        status = manager.status()
        assert status.state == QuiesceState.IDLE
        assert status.is_quiesced is False
        assert status.suspended_task_count == 0
        assert status.active_fallback is None

    def test_quiesce_empty_constellation(self, manager: ConstellationManager) -> None:
        """Verify quiesce when no active tasks are registered."""
        result = manager.quiesce(reason="Outage drill")
        assert result.success is True
        assert result.state == QuiesceState.QUIESCED
        assert result.suspended_count == 0
        assert Path(result.snapshot_path).is_file()

        # Check status reflects quiesced
        status = manager.status()
        assert status.state == QuiesceState.QUIESCED
        assert status.is_quiesced is True
        assert status.reason == "Outage drill"

    def test_quiesce_with_registered_tasks(self, manager: ConstellationManager) -> None:
        """Verify quiesce cleanly captures and persists registered tasks."""
        manager.register_task(
            task_id="rev-01",
            task_type=AgentTaskType.REVIEW_LOOP,
            name="ci-branch-reviewer",
            provider="openai",
            model="gpt-4o",
            state_payload={"iteration": 3},
        )
        manager.register_task(
            task_id="cron-01",
            task_type=AgentTaskType.CRON_JOB,
            name="security-hourly-audit",
            provider="anthropic",
            model="claude-3-5-haiku",
            state_payload={"last_run": "2026-09-08T11:00:00Z"},
        )

        result = manager.quiesce(reason="Provider HTTP 429 flood")
        assert result.success is True
        assert result.suspended_count == 2

        # Verify disk snapshot content
        snapshot_file = Path(result.snapshot_path)
        assert snapshot_file.is_file()
        raw_data = json.loads(snapshot_file.read_text(encoding="utf-8"))
        assert raw_data["state"] == "quiesced"
        assert len(raw_data["tasks"]) == 2
        assert raw_data["tasks"][0]["task_id"] == "rev-01"
        assert raw_data["tasks"][0]["status"] == "suspended"

    def test_quiesce_dry_run(self, manager: ConstellationManager, test_data_dir: Path) -> None:
        """Verify dry run does not write snapshot to disk or mutate in-memory state."""
        task = manager.register_task(
            task_id="rev-01",
            task_type=AgentTaskType.REVIEW_LOOP,
            name="ci-reviewer",
            provider="openai",
            model="gpt-4o",
        )
        assert task.status == "active"
        assert task.suspended_at is None

        result = manager.quiesce(reason="Simulation drill", dry_run=True)
        assert result.success is True
        assert result.suspended_count == 1
        snapshot_path = test_data_dir / "agent" / "quiesce.json"
        assert not snapshot_path.exists()
        assert manager.status().state == QuiesceState.IDLE
        # In-memory registered task must remain untouched
        assert task.status == "active"
        assert task.suspended_at is None

    def test_failover_execution(self, manager: ConstellationManager) -> None:
        """Verify failover re-routes suspended tasks to fallback provider/model."""
        manager.register_task(
            task_id="task-cloud-1",
            task_type=AgentTaskType.SUBAGENT,
            name="ast-code-scout",
            provider="openai",
            model="gpt-4o",
        )
        manager.quiesce(reason="OpenAI upstream timeout")

        res = manager.failover(
            target_provider="ollama",
            target_model="qwen2.5-coder:7b",
        )
        assert res.success is True
        assert res.state == QuiesceState.FAILOVER
        assert res.target_provider == "ollama"
        assert res.target_model == "qwen2.5-coder:7b"
        assert res.rerouted_count == 1

        # Check status
        status = manager.status()
        assert status.state == QuiesceState.FAILOVER
        assert status.active_fallback == ("ollama", "qwen2.5-coder:7b")
        assert len(status.tasks) == 1
        assert status.tasks[0].fallback_provider == "ollama"
        assert status.tasks[0].fallback_model == "qwen2.5-coder:7b"
        assert status.tasks[0].status == "failed_over"

        # Check active route helper
        route = manager.get_active_route("openai", "gpt-4o")
        assert route == ("ollama", "qwen2.5-coder:7b")

    def test_failover_dry_run(self, manager: ConstellationManager) -> None:
        """Verify failover dry run does not persist changes to disk or mutate in-memory state."""
        task = manager.register_task(
            task_id="task-failover-dry",
            task_type=AgentTaskType.SUBAGENT,
            name="dry-runner",
            provider="openai",
            model="gpt-4o",
        )
        manager.quiesce(reason="Outage")
        assert task.fallback_provider is None

        res = manager.failover(
            target_provider="ollama",
            target_model="qwen2.5-coder:7b",
            dry_run=True,
        )
        assert res.success is True
        assert manager.status().state == QuiesceState.QUIESCED
        # Registered task must not have fallback applied
        assert task.fallback_provider is None
        assert task.status == "suspended"

    def test_resume_execution(self, manager: ConstellationManager) -> None:
        """Verify resume restores tasks to active status and clears quiesced state."""
        manager.register_task(
            task_id="worker-1",
            task_type=AgentTaskType.SLOT_WORKER,
            name="symbol-indexer",
            provider="anthropic",
            model="claude-3-7-sonnet",
        )
        manager.quiesce(reason="Maintenance")
        manager.failover(target_provider="ollama", target_model="qwen2.5-coder:7b")

        resume_res = manager.resume()
        assert resume_res.success is True
        assert resume_res.state == QuiesceState.RESUMED
        assert resume_res.resumed_count == 1

        status = manager.status()
        assert status.state == QuiesceState.RESUMED
        assert status.is_quiesced is False
        assert status.tasks[0].status == "resumed"

    def test_resume_dry_run(self, manager: ConstellationManager) -> None:
        """Verify resume dry run does not mutate disk snapshot or in-memory state."""
        task = manager.register_task(
            task_id="worker-resume-dry",
            task_type=AgentTaskType.SLOT_WORKER,
            name="symbol-worker",
            provider="anthropic",
            model="claude-3-7-sonnet",
        )
        manager.quiesce(reason="Maintenance")
        assert task.resumed_at is None

        res = manager.resume(dry_run=True)
        assert res.success is True
        assert manager.status().state == QuiesceState.QUIESCED
        assert task.resumed_at is None
        assert task.status == "suspended"

    def test_status_suspended_task_count_reporting(self, manager: ConstellationManager) -> None:
        """Verify suspended_task_count is 0 when idle/resumed, and matches count when quiesced."""
        manager.register_task(
            task_id="active-task-1",
            task_type=AgentTaskType.REVIEW_LOOP,
            name="live-reviewer",
            provider="openai",
            model="gpt-4o",
        )
        # In IDLE, registered tasks exist but suspended_task_count must be 0
        idle_st = manager.status()
        assert idle_st.state == QuiesceState.IDLE
        assert idle_st.suspended_task_count == 0
        assert len(idle_st.tasks) == 1

        # In QUIESCED, suspended_task_count is 1
        manager.quiesce(reason="Drill")
        q_st = manager.status()
        assert q_st.state == QuiesceState.QUIESCED
        assert q_st.suspended_task_count == 1

        # In FAILOVER, suspended_task_count is 1
        manager.failover(target_provider="ollama", target_model="qwen2.5-coder:7b")
        f_st = manager.status()
        assert f_st.state == QuiesceState.FAILOVER
        assert f_st.suspended_task_count == 1

        # In RESUMED, suspended_task_count drops back to 0
        manager.resume()
        r_st = manager.status()
        assert r_st.state == QuiesceState.RESUMED
        assert r_st.suspended_task_count == 0

    def test_atomic_snapshot_write_failure_cleanup(
        self, manager: ConstellationManager, test_data_dir: Path
    ) -> None:
        """Verify atomic write cleans up temporary file if os.replace fails."""
        from devops_cli.ai.controller.manager import _write_snapshot_file

        snapshot = QuiesceSnapshot(
            state=QuiesceState.QUIESCED,
            reason="Atomic test",
        )
        target = test_data_dir / "agent" / "quiesce.json"

        with patch("os.replace", side_effect=OSError("Disk full simulation")):
            with pytest.raises(OSError, match="Disk full simulation"):
                _write_snapshot_file(target, snapshot)

        # Confirm no leftover .tmp files
        agent_dir = test_data_dir / "agent"
        tmp_files = list(agent_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_corrupted_snapshot_handling(
        self, manager: ConstellationManager, test_data_dir: Path
    ) -> None:
        """Verify graceful fallback when snapshot file is corrupted."""
        snapshot_file = test_data_dir / "agent" / "quiesce.json"
        snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        snapshot_file.write_text("invalid json {{{", encoding="utf-8")

        status = manager.status()
        assert status.state == QuiesceState.IDLE
        assert status.is_quiesced is False

    def test_telemetry_instrumentation(self, manager: ConstellationManager) -> None:
        """Verify OpenTelemetry span emission and Prometheus metric updates without high-cardinality labels."""
        with (
            patch("devops_cli.ai.controller.manager.trace_span") as mock_span,
            patch(
                "devops_cli.ai.controller.manager.devops_cli_ai_quiesce_events_total"
            ) as mock_counter,
        ):
            mock_span.return_value.__enter__ = MagicMock()
            mock_span.return_value.__exit__ = MagicMock()
            manager.quiesce(reason="Telemetry test")
            mock_span.assert_called()
            mock_counter.inc.assert_called_once_with()

    def test_manager_helpers_and_route_fallback(
        self, manager: ConstellationManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify unregister_task, is_quiesced, and route fallback when not failed over."""
        task = manager.register_task(
            task_id="temp-1",
            task_type=AgentTaskType.SUBAGENT,
            name="temp-agent",
            provider="openai",
            model="gpt-4o",
        )
        assert task.task_id == "temp-1"
        assert manager.is_quiesced() is False

        # Route fallback returns original route when not in FAILOVER state
        route = manager.get_active_route("openai", "gpt-4o")
        assert route == ("openai", "gpt-4o")

        # Unregister task
        assert manager.unregister_task("temp-1") is True
        assert manager.unregister_task("nonexistent") is False

        # Default data dir resolution without env
        monkeypatch.delenv("DEVOPS_CLI_DATA_DIR", raising=False)
        default_mgr = ConstellationManager()
        assert default_mgr.data_dir is not None


class TestConstellationCLI:
    """Test Typer CLI subcommands for devops ai quiesce, failover, resume, constellation."""

    @pytest.fixture(autouse=True)
    def clean_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure isolated data directory for CLI runs."""
        monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(tmp_path / ".data"))

    def test_cli_constellation_status_idle(self) -> None:
        """Verify devops ai constellation prints status."""
        result = runner.invoke(app, ["ai", "constellation"])
        assert result.exit_code == 0
        assert "IDLE" in result.stdout or "Status" in result.stdout

    def test_cli_constellation_status_json(self) -> None:
        """Verify devops ai constellation --format json."""
        result = runner.invoke(app, ["ai", "constellation", "--format", "json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["state"] == "idle"

    def test_cli_quiesce_dry_run(self) -> None:
        """Verify devops ai quiesce --dry-run."""
        result = runner.invoke(
            app, ["ai", "quiesce", "--reason", "Dry-run test drill", "--dry-run"]
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout or "simulated" in result.stdout.lower()

    def test_cli_quiesce_live(self) -> None:
        """Verify devops ai quiesce execution and status reflection."""
        result = runner.invoke(app, ["ai", "quiesce", "--reason", "Provider failure drill"])
        assert result.exit_code == 0
        assert "QUIESCED" in result.stdout

        # Verify status
        status_res = runner.invoke(app, ["ai", "constellation", "--format", "json"])
        assert status_res.exit_code == 0
        payload = json.loads(status_res.stdout)
        assert payload["state"] == "quiesced"
        assert payload["reason"] == "Provider failure drill"

    def test_cli_failover_dry_run(self) -> None:
        """Verify devops ai failover --dry-run."""
        result = runner.invoke(
            app,
            [
                "ai",
                "failover",
                "--target-provider",
                "ollama",
                "--target-model",
                "qwen2.5-coder:7b",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout or "simulated" in result.stdout.lower()

    def test_cli_failover_live(self) -> None:
        """Verify devops ai failover updates route."""
        runner.invoke(app, ["ai", "quiesce", "--reason", "Cloud outage"])
        result = runner.invoke(
            app,
            [
                "ai",
                "failover",
                "--target-provider",
                "ollama",
                "--target-model",
                "qwen2.5-coder:7b",
            ],
        )
        assert result.exit_code == 0
        assert "FAILOVER" in result.stdout or "qwen2.5-coder:7b" in result.stdout

    def test_cli_resume_dry_run(self) -> None:
        """Verify devops ai resume --dry-run."""
        runner.invoke(app, ["ai", "quiesce", "--reason", "Pre-resume"])
        result = runner.invoke(app, ["ai", "resume", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout or "simulated" in result.stdout.lower()

    def test_cli_resume_live(self) -> None:
        """Verify devops ai resume restores state."""
        runner.invoke(app, ["ai", "quiesce", "--reason", "Pre-resume"])
        result = runner.invoke(app, ["ai", "resume"])
        assert result.exit_code == 0
        assert "RESUMED" in result.stdout or "resumed" in result.stdout.lower()

    def test_cli_quiesce_invalid_drain_timeout(self) -> None:
        """Verify error exit when drain timeout is negative."""
        result = runner.invoke(app, ["ai", "quiesce", "--drain-timeout", "-1.0"])
        assert result.exit_code == 1
        assert "non-negative" in result.output

    def test_cli_failover_and_resume_json(self) -> None:
        """Verify json formatting for failover and resume commands."""
        runner.invoke(app, ["ai", "quiesce", "--reason", "JSON drill"])
        f_res = runner.invoke(
            app,
            [
                "ai",
                "failover",
                "--target-provider",
                "ollama",
                "--target-model",
                "qwen2.5-coder:7b",
                "--format",
                "json",
            ],
        )
        assert f_res.exit_code == 0
        f_data = json.loads(f_res.stdout)
        assert f_data["state"] == "failover"

        r_res = runner.invoke(app, ["ai", "resume", "--format", "json"])
        assert r_res.exit_code == 0
        r_data = json.loads(r_res.stdout)
        assert r_data["state"] == "resumed"

    def test_cli_constellation_with_tasks_table(self, tmp_path: Path) -> None:
        """Verify table rendering when tasks are present in snapshot."""
        mgr = ConstellationManager(data_dir=tmp_path / ".data")
        mgr.register_task(
            task_id="t-table-1",
            task_type=AgentTaskType.REVIEW_LOOP,
            name="test-worker",
            provider="openai",
            model="gpt-4o",
        )
        mgr.quiesce(reason="Rendering test")
        res = runner.invoke(app, ["ai", "constellation"])
        assert res.exit_code == 0
        assert "t-table-1" in res.stdout or "Agent Constellation Tasks" in res.stdout

    def test_resolve_data_dir_rejects_forbidden_system_paths(self) -> None:
        """Verify _resolve_data_dir raises SecurityError on forbidden system directories."""
        from devops_cli.ai.controller.manager import _resolve_data_dir
        from devops_cli.exceptions.security import SecurityError

        with pytest.raises(
            SecurityError, match="Data directory cannot be located in forbidden system path"
        ):
            _resolve_data_dir("/etc")
