"""Tests for the agent constellation flag: quiesce, record a fallback route, and clear."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.controller.manager import ConstellationManager, _write_snapshot_file
from devops_cli.ai.controller.models import (
    ConstellationStatus,
    QuiesceSnapshot,
    QuiesceState,
)
from devops_cli.exceptions.ai import (
    ConstellationFailoverError,
    ConstellationQuiesceError,
    ConstellationResumeError,
)
from devops_cli.main import app

runner = CliRunner()


def test_enum_values() -> None:
    assert [state.value for state in QuiesceState] == ["idle", "quiesced", "failover", "resumed"]


def test_the_flag_holds_no_tasks() -> None:
    """Nothing registers tasks, so the flag records only state, reason and a fallback route."""
    snapshot_fields = set(QuiesceSnapshot.model_fields)
    status_fields = set(ConstellationStatus.model_fields)
    assert ({"tasks"} & snapshot_fields, {"tasks", "suspended_task_count"} & status_fields) == (
        set(),
        set(),
    )


def test_domain_exceptions() -> None:
    q_err = ConstellationQuiesceError("Failed quiescing", reason="timeout")
    f_err = ConstellationFailoverError(
        "Failed failover", target_provider="ollama", target_model="qwen"
    )
    r_err = ConstellationResumeError("Failed resuming")
    assert (q_err.details["reason"], f_err.details["target_provider"], str(r_err)) == (
        "timeout",
        "ollama",
        "Failed resuming",
    )


class TestConstellationManager:
    """The manager writes and reads the flag in the data directory."""

    @pytest.fixture
    def data_dir(self, tmp_path: Path) -> Path:
        return tmp_path / ".data"

    @pytest.fixture
    def manager(self, data_dir: Path) -> ConstellationManager:
        return ConstellationManager(data_dir=data_dir)

    def test_initial_status_is_idle(self, manager: ConstellationManager) -> None:
        status = manager.status()
        assert (status.state, status.is_quiesced, status.active_fallback) == (
            QuiesceState.IDLE,
            False,
            None,
        )

    def test_quiesce_sets_the_flag_with_its_reason(self, manager: ConstellationManager) -> None:
        result = manager.quiesce(reason="Upstream outage")
        status = manager.status()
        assert (result.state, status.state, status.is_quiesced, status.reason) == (
            QuiesceState.QUIESCED,
            QuiesceState.QUIESCED,
            True,
            "Upstream outage",
        )

    def test_a_dry_run_writes_no_flag(self, manager: ConstellationManager) -> None:
        manager.quiesce(reason="dry", dry_run=True)
        manager.failover(dry_run=True)
        manager.resume(dry_run=True)
        assert (manager.snapshot_file.exists(), manager.status().state) == (
            False,
            QuiesceState.IDLE,
        )

    def test_failover_records_the_fallback_and_keeps_the_reason(
        self, manager: ConstellationManager
    ) -> None:
        manager.quiesce(reason="Provider outage")
        manager.failover(target_provider="ollama", target_model="qwen2.5-coder:7b")
        status = manager.status()
        assert (status.state, status.reason, status.active_fallback) == (
            QuiesceState.FAILOVER,
            "Provider outage",
            ("ollama", "qwen2.5-coder:7b"),
        )

    def test_resume_clears_the_flag(self, manager: ConstellationManager) -> None:
        manager.failover(target_provider="ollama", target_model="qwen2.5-coder:7b")
        result = manager.resume()
        status = manager.status()
        assert (result.message, status.state, status.is_quiesced, status.active_fallback) == (
            "Quiesce and failover flag cleared.",
            QuiesceState.RESUMED,
            False,
            None,
        )

    def test_resume_without_a_flag_says_so(self, manager: ConstellationManager) -> None:
        assert manager.resume().message == "No quiesce or failover flag was set."

    def test_atomic_snapshot_write_failure_cleanup(self, data_dir: Path) -> None:
        """A failed atomic write leaves no temporary file behind."""
        target = data_dir / "agent" / "quiesce.json"
        snapshot = QuiesceSnapshot(state=QuiesceState.QUIESCED, reason="Atomic test")
        with (
            patch("os.replace", side_effect=OSError("Disk full simulation")),
            pytest.raises(OSError, match="Disk full simulation"),
        ):
            _write_snapshot_file(target, snapshot)
        assert list((data_dir / "agent").glob("*.tmp")) == []

    def test_a_corrupted_flag_reads_as_idle(
        self, manager: ConstellationManager, data_dir: Path
    ) -> None:
        snapshot_file = data_dir / "agent" / "quiesce.json"
        snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        snapshot_file.write_text("invalid json {{{", encoding="utf-8")
        assert (manager.status().state, manager.status().is_quiesced) == (QuiesceState.IDLE, False)

    def test_telemetry_instrumentation(self, manager: ConstellationManager) -> None:
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

    def test_resolve_data_dir_rejects_forbidden_system_paths(self) -> None:
        from devops_cli.ai.controller.manager import _resolve_data_dir
        from devops_cli.exceptions.security import SecurityError

        with pytest.raises(
            SecurityError, match="Data directory cannot be located in forbidden system path"
        ):
            _resolve_data_dir("/etc")


class TestConstellationCLI:
    """The CLI shows the flag as written, by these commands or by anything else."""

    @pytest.fixture(autouse=True)
    def data_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        data = tmp_path / ".data"
        monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(data))
        return data

    def test_constellation_shows_the_flag_written_to_quiesce_json(self, data_dir: Path) -> None:
        """Changing quiesce.json changes what `ai constellation` reports."""
        idle = runner.invoke(app, ["ai", "constellation", "--format", "json"])
        snapshot = QuiesceSnapshot(
            state=QuiesceState.FAILOVER,
            reason="Gateway down",
            active_fallback=("ollama", "qwen2.5-coder:7b"),
        )
        _write_snapshot_file(data_dir / "agent" / "quiesce.json", snapshot)
        flagged = runner.invoke(app, ["ai", "constellation", "--format", "json"])
        before, after = json.loads(idle.stdout), json.loads(flagged.stdout)
        assert (before["state"], after["state"], after["reason"], after["active_fallback"]) == (
            "idle",
            "failover",
            "Gateway down",
            ["ollama", "qwen2.5-coder:7b"],
        )

    def test_constellation_says_the_flag_only_records_intent(self) -> None:
        result = runner.invoke(app, ["ai", "constellation"])
        assert (result.exit_code, "no running task reads it" in result.stdout) == (0, True)

    def test_quiesce_failover_and_resume_round_trip(self) -> None:
        quiesce = runner.invoke(app, ["ai", "quiesce", "--reason", "Maintenance"])
        failover = runner.invoke(
            app,
            ["ai", "failover", "--target-provider", "ollama", "--target-model", "qwen2.5-coder:7b"],
        )
        resume = runner.invoke(app, ["ai", "resume"])
        status = json.loads(runner.invoke(app, ["ai", "constellation", "--format", "json"]).stdout)
        assert (
            quiesce.exit_code,
            "Maintenance" in quiesce.stdout,
            failover.exit_code,
            "gateway failover" in failover.stdout,
            resume.exit_code,
            "cleared" in resume.stdout,
            status["state"],
        ) == (0, True, 0, True, 0, True, "resumed")

    def test_json_results_carry_no_task_counts(self) -> None:
        payloads = [
            json.loads(runner.invoke(app, ["ai", *args, "--format", "json"]).stdout)
            for args in (["quiesce"], ["failover"], ["resume"])
        ]
        counts = {"suspended_count", "rerouted_count", "resumed_count"}
        assert [counts & set(p) for p in payloads] == [set(), set(), set()]

    def test_removed_options_are_rejected(self) -> None:
        """--force and --drain-timeout acted on tasks that no longer exist."""
        force = runner.invoke(app, ["ai", "failover", "--force"])
        drain = runner.invoke(app, ["ai", "quiesce", "--drain-timeout", "5"])
        assert (force.exit_code, drain.exit_code) == (2, 2)
