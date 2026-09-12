"""Submodule-aligned test suite for sandbox streaming logs and panic detection."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.sandbox import app
from devops_cli.exceptions.sandbox import SandboxNotFoundError
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.logs import (
    archive_incident,
    detect_panics,
    parse_docker_log_line,
)
from devops_cli.sandbox.models import (
    PanicIncident,
    PanicType,
    SandboxInstance,
    SandboxLogLine,
    SandboxLogsReport,
    SandboxStatus,
)

runner = CliRunner()


def _make_dummy_instance(
    instance_id: str = "sandbox-web-123456",
    container_id: str = "docker-cont-789",
    name: str = "web-svc",
) -> SandboxInstance:
    """Create standard test SandboxInstance."""
    return SandboxInstance(
        instance_id=instance_id,
        container_id=container_id,
        name=name,
        image="python:3.14-slim",
        status=SandboxStatus.RUNNING,
        workspace_dir="/workspace",
        created_at="2026-09-12T20:00:00Z",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Models & Archiving Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_panic_incident_model_message_capping() -> None:
    """Ensure message length is capped at 256 characters per security invariant."""
    long_msg = "X" * 500
    incident = PanicIncident(
        incident_id="incident-001",
        instance_id="inst-1",
        container_id="cont-1",
        panic_type=PanicType.PYTHON_TRACEBACK,
        message=long_msg,
        stacktrace=["line 1", "line 2"],
    )
    assert len(incident.message) == 256
    assert incident.message == "X" * 256


def test_archive_incident_persistence(tmp_path: Path) -> None:
    """Verify incident JSON persistence and path return."""
    incident = PanicIncident(
        incident_id="incident-test1234",
        instance_id="inst-test",
        container_id="cont-test",
        panic_type=PanicType.GO_PANIC,
        message="panic: index out of bounds",
        stacktrace=["panic: index out of bounds", "goroutine 1 [running]:"],
    )
    saved_path = archive_incident(incident, base_dir=tmp_path)
    assert saved_path.exists()
    assert saved_path.name == "incident-test1234.json"

    data = json.loads(saved_path.read_text(encoding="utf-8"))
    assert data["incident_id"] == "incident-test1234"
    assert data["panic_type"] == "go_panic"
    assert data["message"] == "panic: index out of bounds"


def test_archive_incident_path_traversal_rejection(tmp_path: Path) -> None:
    """Verify path traversal sequences in incident IDs are rejected."""
    incident = PanicIncident(
        incident_id="../../malicious",
        instance_id="inst-test",
        container_id="cont-test",
        panic_type=PanicType.SEGFAULT,
        message="segfault",
    )
    with pytest.raises(Exception):
        archive_incident(incident, base_dir=tmp_path)


# ─────────────────────────────────────────────────────────────────────────────
# 2. PanicDetector Unit Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_detect_python_traceback() -> None:
    """Verify detection of Python tracebacks."""
    lines = [
        "Starting application server on 0.0.0.0:8080...",
        "Traceback (most recent call last):",
        '  File "/app/server.py", line 42, in handle_request',
        "    result = 1 / 0",
        "ZeroDivisionError: division by zero",
        "Worker process died unexpectedly.",
    ]
    incidents = detect_panics(lines, instance_id="inst-py", container_id="cont-py")
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.panic_type == PanicType.PYTHON_TRACEBACK
    assert "ZeroDivisionError" in inc.message
    assert len(inc.stacktrace) >= 4


def test_detect_go_panic() -> None:
    """Verify detection of Go runtime panics."""
    lines = [
        "2026/09/12 20:00:00 Listening on :8080",
        "panic: runtime error: index out of range [3] with length 2",
        "",
        "goroutine 1 [running]:",
        "main.handleRequest(0xc00008e000)",
        "\t/go/src/app/main.go:25 +0x1a4",
        "main.main()",
        "\t/go/src/app/main.go:12 +0x45",
    ]
    incidents = detect_panics(lines, instance_id="inst-go", container_id="cont-go")
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.panic_type == PanicType.GO_PANIC
    assert "index out of range" in inc.message
    assert len(inc.stacktrace) >= 4


def test_detect_java_stacktrace() -> None:
    """Verify detection of Java runtime exceptions and stacktraces."""
    lines = [
        'Exception in thread "main" java.lang.NullPointerException: Value is null',
        "\tat com.example.demo.App.process(App.java:34)",
        "\tat com.example.demo.App.main(App.java:12)",
    ]
    incidents = detect_panics(lines, instance_id="inst-java", container_id="cont-java")
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.panic_type == PanicType.JAVA_STACKTRACE
    assert "NullPointerException" in inc.message
    assert len(inc.stacktrace) == 3


def test_detect_rust_panic() -> None:
    """Verify detection of Rust panics."""
    lines = [
        "thread 'main' panicked at 'called `Option::unwrap()` on a `None` value', src/main.rs:14:28",
        "stack backtrace:",
        "   0: rust_begin_unwind",
        "   1: core::panicking::panic_fmt",
        "   2: myapp::main",
    ]
    incidents = detect_panics(lines, instance_id="inst-rs", container_id="cont-rs")
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.panic_type == PanicType.RUST_PANIC
    assert "Option::unwrap" in inc.message


def test_detect_segfault() -> None:
    """Verify detection of fatal segfaults and signals."""
    lines = [
        "Initializing native library...",
        "Segmentation fault (core dumped)",
    ]
    incidents = detect_panics(lines, instance_id="inst-c", container_id="cont-c")
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.panic_type == PanicType.SEGFAULT
    assert "Segmentation fault" in inc.message


def test_parse_docker_log_line_with_timestamp() -> None:
    """Verify timestamp extraction from Docker log lines."""
    raw = "2026-09-12T20:15:30.123456789Z [INFO] Server started"
    parsed = parse_docker_log_line(raw, default_stream="stdout")
    assert parsed.timestamp == "2026-09-12T20:15:30.123456789Z"
    assert parsed.content == "[INFO] Server started"
    assert parsed.stream == "stdout"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Engine Logs Method Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_engine_logs_success(tmp_path: Path) -> None:
    """Verify WorkloadSandboxEngine.logs retrieves and parses logs with incidents."""
    inst = _make_dummy_instance()
    engine = WorkloadSandboxEngine()
    engine.status = MagicMock(return_value=[inst])  # type: ignore[assignment]

    mock_container = MagicMock()
    mock_container.logs.return_value = (
        b"Traceback (most recent call last):\n"
        b'  File "app.py", line 2, in <module>\n'
        b"ZeroDivisionError: division by zero\n"
    )

    with patch("devops_cli.sandbox.engine._get_docker_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        report = engine.logs(
            identifier=inst.instance_id,
            tail=50,
            detect_panics_flag=True,
            incident_dir=tmp_path,
        )

        assert report.instance_id == inst.instance_id
        assert report.total_lines == 3
        assert report.panics_detected == 1
        assert len(report.incidents) == 1
        assert report.incidents[0].panic_type == PanicType.PYTHON_TRACEBACK


def test_engine_logs_not_found() -> None:
    """Verify engine raises SandboxNotFoundError when identifier doesn't exist."""
    engine = WorkloadSandboxEngine()
    engine.status = MagicMock(return_value=[])  # type: ignore[assignment]

    with pytest.raises(SandboxNotFoundError):
        engine.logs(identifier="nonexistent-sandbox")


# ─────────────────────────────────────────────────────────────────────────────
# 4. CLI Command Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_sandbox_logs_json_output(tmp_path: Path) -> None:
    """Verify devops sandbox logs --json outputs valid structured JSON."""
    inst = _make_dummy_instance()
    engine = WorkloadSandboxEngine()
    engine.status = MagicMock(return_value=[inst])  # type: ignore[assignment]

    mock_report = SandboxLogsReport(
        instance_id=inst.instance_id,
        container_id=inst.container_id,
        total_lines=2,
        panics_detected=0,
        lines=[
            SandboxLogLine(content="Server initializing"),
            SandboxLogLine(content="Ready on http://example.com:8080"),
        ],
    )

    with patch("devops_cli.commands.sandbox.WorkloadSandboxEngine") as mock_engine_cls:
        mock_eng = MagicMock()
        mock_eng.status.return_value = [inst]
        mock_eng.logs.return_value = mock_report
        mock_engine_cls.return_value = mock_eng

        res = runner.invoke(app, ["logs", inst.instance_id, "--json"])
        assert res.exit_code == 0
        data = json.loads(res.stdout)
        assert data["instance_id"] == inst.instance_id
        assert data["total_lines"] == 2
        assert data["panics_detected"] == 0


def test_cli_sandbox_logs_dry_run() -> None:
    """Verify devops sandbox logs with --dry-run prints simulation output."""
    inst = _make_dummy_instance()
    with patch("devops_cli.commands.sandbox.WorkloadSandboxEngine") as mock_engine_cls:
        mock_eng = MagicMock()
        mock_eng.status.return_value = [inst]
        mock_engine_cls.return_value = mock_eng

        res = runner.invoke(app, ["logs", inst.instance_id, "--dry-run"])
        assert "DRY_RUN" in res.stdout or "stream_sandbox_logs" in res.stdout


def test_cli_sandbox_logs_panic_alert_display(tmp_path: Path) -> None:
    """Verify devops sandbox logs renders panic alert panel when a crash is detected."""
    inst = _make_dummy_instance()
    incident = PanicIncident(
        incident_id="inc-alert-1234",
        instance_id=inst.instance_id,
        container_id=inst.container_id,
        panic_type=PanicType.PYTHON_TRACEBACK,
        message="ZeroDivisionError: division by zero",
        stacktrace=["Traceback:", "ZeroDivisionError: division by zero"],
        archived_path=str(tmp_path / "inc-alert-1234.json"),
    )
    mock_report = SandboxLogsReport(
        instance_id=inst.instance_id,
        container_id=inst.container_id,
        total_lines=2,
        panics_detected=1,
        incidents=[incident],
        lines=[
            SandboxLogLine(content="Traceback (most recent call last):", is_panic=True),
            SandboxLogLine(content="ZeroDivisionError: division by zero", is_panic=True),
        ],
    )

    with patch("devops_cli.commands.sandbox.WorkloadSandboxEngine") as mock_engine_cls:
        mock_eng = MagicMock()
        mock_eng.status.return_value = [inst]
        mock_eng.logs.return_value = mock_report
        mock_engine_cls.return_value = mock_eng

        res = runner.invoke(app, ["logs", inst.instance_id])
        assert res.exit_code == 0
        assert "ZeroDivisionError" in res.stdout
        assert "python_traceback" in res.stdout or "CRITICAL" in res.stdout


def test_engine_logs_subprocess_fallback(tmp_path: Path) -> None:
    """Verify engine falls back to CLI subprocess when Docker SDK throws an exception."""
    inst = _make_dummy_instance()
    engine = WorkloadSandboxEngine()
    engine.status = MagicMock(return_value=[inst])  # type: ignore[assignment]

    with (
        patch(
            "devops_cli.sandbox.engine._get_docker_client",
            side_effect=RuntimeError("Docker daemon down"),
        ),
        patch("devops_cli.sandbox.engine.run_subprocess") as mock_run_proc,
    ):
        mock_proc = MagicMock()
        mock_proc.stdout = "2026-09-12T20:20:00.000Z Fallback log output 1\nFallback log output 2\n"
        mock_proc.stderr = ""
        mock_run_proc.return_value = mock_proc

        report = engine.logs(identifier=inst.instance_id, detect_panics_flag=False)
        assert report.total_lines == 2
        assert report.lines[0].content == "Fallback log output 1"


def test_engine_logs_generator_stream() -> None:
    """Verify engine handles generator byte chunks from container logs."""
    inst = _make_dummy_instance()
    engine = WorkloadSandboxEngine()
    engine.status = MagicMock(return_value=[inst])  # type: ignore[assignment]

    mock_container = MagicMock()
    mock_container.logs.return_value = [b"stream chunk 1\n", b"stream chunk 2\n"]

    with patch("devops_cli.sandbox.engine._get_docker_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container
        mock_get_client.return_value = mock_client

        report = engine.logs(identifier=inst.instance_id, follow=True)
        assert report.total_lines == 2


def test_resolve_incident_dir_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_incident_dir honors DEVOPS_CLI_DATA_DIR."""
    from devops_cli.sandbox.logs import resolve_incident_dir

    custom_data = tmp_path / "custom_data"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(custom_data))
    resolved = resolve_incident_dir()
    assert resolved == custom_data / "sandbox" / "incidents"


def test_cli_sandbox_logs_auto_resolve_success() -> None:
    """Verify devops sandbox logs auto-resolves single running container and succeeds."""
    inst = _make_dummy_instance()
    mock_report = SandboxLogsReport(
        instance_id=inst.instance_id,
        container_id=inst.container_id,
        total_lines=1,
        panics_detected=0,
        lines=[SandboxLogLine(content="Application healthy.")],
    )

    with patch("devops_cli.commands.sandbox.WorkloadSandboxEngine") as mock_engine_cls:
        mock_eng = MagicMock()
        mock_eng.status.return_value = [inst]
        mock_eng.logs.return_value = mock_report
        mock_engine_cls.return_value = mock_eng

        res = runner.invoke(app, ["logs"])
        assert res.exit_code == 0
        assert "Application healthy." in res.stdout
        assert "Stream closed" in res.stdout


def test_cli_sandbox_logs_multiple_instances_prompt() -> None:
    """Verify devops sandbox logs prompts error if multiple instances exist without identifier."""
    inst1 = _make_dummy_instance(instance_id="inst-1")
    inst2 = _make_dummy_instance(instance_id="inst-2")

    with patch("devops_cli.commands.sandbox.WorkloadSandboxEngine") as mock_engine_cls:
        mock_eng = MagicMock()
        mock_eng.status.return_value = [inst1, inst2]
        mock_engine_cls.return_value = mock_eng

        res = runner.invoke(app, ["logs"])
        assert res.exit_code == 0
        assert "Multiple sandboxes running" in res.output


def test_cli_sandbox_logs_no_instances_prompt() -> None:
    """Verify devops sandbox logs prompts error when no sandboxes are deployed."""
    with patch("devops_cli.commands.sandbox.WorkloadSandboxEngine") as mock_engine_cls:
        mock_eng = MagicMock()
        mock_eng.status.return_value = []
        mock_engine_cls.return_value = mock_eng

        res = runner.invoke(app, ["logs"])
        assert res.exit_code == 0
        assert "No running or deployed sandbox instances found" in res.output
