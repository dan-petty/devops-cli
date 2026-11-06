"""Submodule-aligned test suite for sandbox streaming logs and panic detection."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import requests

from devops_cli.exceptions.docker import DockerEngineError
from devops_cli.exceptions.sandbox import SandboxNotFoundError
from devops_cli.exceptions.security import SecurityError
from devops_cli.sandbox.engine import MAX_FOLLOW_BUFFER_LINES, WorkloadSandboxEngine
from devops_cli.sandbox.logs import (
    archive_incident,
    detect_panics,
    parse_docker_log_line,
)
from devops_cli.sandbox.models import (
    PanicIncident,
    PanicType,
    SandboxInstance,
)
from tests.support.fakes.docker_engine import LOG_TIME, DockerEngineFake

_TRACEBACK = (
    b"Traceback (most recent call last):\n"
    b'  File "app.py", line 2, in <module>\n'
    b"ZeroDivisionError: division by zero\n"
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
    assert oct(saved_path.stat().st_mode & 0o777) == oct(0o600)
    assert oct(saved_path.parent.stat().st_mode & 0o777) == oct(0o700)

    data = json.loads(saved_path.read_text(encoding="utf-8"))
    assert data["incident_id"] == "incident-test1234"
    assert data["panic_type"] == "go_panic"
    assert data["message"] == "panic: index out of bounds"


def test_archive_incident_secret_masking(tmp_path: Path) -> None:
    """Verify secrets in incident message and stacktrace are masked when archived."""
    incident = PanicIncident(
        incident_id="incident-secret-test",
        instance_id="inst-sec",
        container_id="cont-sec",
        panic_type=PanicType.PYTHON_TRACEBACK,
        message="Failure with token=ghp_1234567890abcdef1234",
        stacktrace=["Traceback:", "RuntimeError: password=mysecretpassword123"],
    )
    saved_path = archive_incident(incident, base_dir=tmp_path)
    assert saved_path.exists()
    data = json.loads(saved_path.read_text(encoding="utf-8"))
    assert "ghp_1234567890abcdef1234" not in data["message"]
    assert "<masked-github-token>" in data["message"]
    assert "mysecretpassword123" not in data["stacktrace"][1]
    assert "<masked-password>" in data["stacktrace"][1]


def test_archive_incident_path_traversal_rejection(tmp_path: Path) -> None:
    """Verify path traversal sequences in incident IDs are rejected."""
    incident = PanicIncident(
        incident_id="../../malicious",
        instance_id="inst-test",
        container_id="cont-test",
        panic_type=PanicType.SEGFAULT,
        message="segfault",
    )
    with pytest.raises(SecurityError) as raised:
        archive_incident(incident, base_dir=tmp_path)
    assert raised.value.error_code == "SECURITY_ERROR"


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


def test_engine_logs_success(
    tmp_path: Path, register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """Verify WorkloadSandboxEngine.logs retrieves and parses logs with incidents."""
    inst = register_sandbox("sandbox-web-123456", log_frames=[("stdout", _TRACEBACK)])

    report = WorkloadSandboxEngine().logs(
        identifier=inst.instance_id,
        tail=50,
        detect_panics_flag=True,
        incident_dir=tmp_path,
    )

    assert (
        report.instance_id,
        report.total_lines,
        report.panics_detected,
        [incident.panic_type for incident in report.incidents],
    ) == (inst.instance_id, 3, 1, [PanicType.PYTHON_TRACEBACK])


def test_engine_logs_not_found() -> None:
    """Verify engine raises SandboxNotFoundError when identifier doesn't exist."""
    with pytest.raises(SandboxNotFoundError) as raised:
        WorkloadSandboxEngine().logs(identifier="nonexistent-sandbox")
    assert raised.value.error_code == "SANDBOX_NOT_FOUND_ERROR"


# ─────────────────────────────────────────────────────────────────────────────
# 4. CLI Command Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_cli_sandbox_logs_json_output(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """Verify devops sandbox logs --json outputs valid structured JSON."""
    inst = register_sandbox(
        log_frames=[
            ("stdout", b"Server initializing\n"),
            ("stdout", b"Ready on http://example.com:8080\n"),
        ]
    )

    res = cli("sandbox", "logs", inst.instance_id, "--json")

    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert (data["instance_id"], data["total_lines"], data["panics_detected"]) == (
        inst.instance_id,
        2,
        0,
    )


def test_cli_sandbox_logs_dry_run(cli: Callable[..., Any]) -> None:
    """Verify devops sandbox logs with --dry-run prints simulation output."""
    res = cli("sandbox", "logs", "sandbox-web-123456", "--dry-run")

    assert res.exit_code == 0
    assert "Planned requests for devops sandbox logs" in res.stdout


def test_cli_sandbox_logs_panic_alert_display(
    tmp_path: Path, cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """Verify devops sandbox logs renders panic alert panel when a crash is detected."""
    inst = register_sandbox(log_frames=[("stdout", _TRACEBACK)])

    res = cli("sandbox", "logs", inst.instance_id, "--incident-dir", tmp_path)

    assert res.exit_code == 0
    assert "ZeroDivisionError" in res.stdout
    assert "python_traceback" in res.stdout or "CRITICAL" in res.stdout
    assert len(list(tmp_path.glob("incident-*.json"))) == 1


def test_engine_logs_surface_daemon_failure(
    docker_daemon: DockerEngineFake, register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """An Engine API log retrieval failure is surfaced rather than retried via the CLI."""
    inst = register_sandbox(log_frames=[("stdout", b"never read\n")])
    docker_daemon.fail("api.get", requests.exceptions.ConnectionError("engine went away"))

    with pytest.raises(DockerEngineError, match="Container log stream failed"):
        WorkloadSandboxEngine().logs(identifier=inst.instance_id, detect_panics_flag=False)


def test_engine_logs_generator_stream(register_sandbox: Callable[..., SandboxInstance]) -> None:
    """Verify engine reads a followed log frame by frame."""
    inst = register_sandbox(
        log_frames=[("stdout", b"stream chunk 1\n"), ("stdout", b"stream chunk 2\n")]
    )

    report = WorkloadSandboxEngine().logs(identifier=inst.instance_id, follow=True)

    assert [line.content for line in report.lines] == ["stream chunk 1", "stream chunk 2"]


def test_resolve_incident_dir_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify resolve_incident_dir honors DEVOPS_CLI_DATA_DIR and enforces security."""
    from devops_cli.exceptions import SecurityError
    from devops_cli.sandbox.logs import resolve_incident_dir

    custom_data = tmp_path / "custom_data"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(custom_data))
    resolved = resolve_incident_dir()
    assert resolved == custom_data / "sandbox" / "incidents"

    # Forbidden system path
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", "/etc")
    with pytest.raises(SecurityError, match="resolves to a forbidden system path"):
        resolve_incident_dir()

    # Symlink rejection
    real_data = tmp_path / "real_data"
    real_data.mkdir()
    symlink_data = tmp_path / "symlink_data"
    symlink_data.symlink_to(real_data)
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(symlink_data))
    with pytest.raises(SecurityError, match="must not be a symlink"):
        resolve_incident_dir()


def test_cli_sandbox_logs_auto_resolve_success(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """Verify devops sandbox logs auto-resolves single running container and succeeds."""
    register_sandbox(log_frames=[("stdout", b"Application healthy.\n")])

    res = cli("sandbox", "logs")

    assert res.exit_code == 0
    assert "Application healthy." in res.stdout
    assert "Stream closed" in res.stdout


def test_cli_sandbox_logs_multiple_instances_prompt(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """Verify devops sandbox logs prompts error if multiple instances exist without identifier."""
    register_sandbox("inst-1")
    register_sandbox("inst-2")

    res = cli("sandbox", "logs")

    assert res.exit_code == 1
    assert "Multiple sandboxes running" in res.output


def test_cli_sandbox_logs_no_instances_prompt(
    cli: Callable[..., Any], docker_daemon: DockerEngineFake
) -> None:
    """Verify devops sandbox logs prompts error when no sandboxes are deployed."""
    res = cli("sandbox", "logs")

    assert res.exit_code == 1
    assert "No running or deployed sandbox instances found" in res.output


def test_archive_incident_nested_or_absolute_traversal_rejection(tmp_path: Path) -> None:
    """Verify nested subdirectories and absolute paths in incident_id are rejected."""
    from devops_cli.exceptions.security import SecurityError

    for bad_id in (str(tmp_path / "evil"), "sub/dir", "a\\b", ".."):
        incident = PanicIncident(
            incident_id=bad_id,
            instance_id="inst-test",
            container_id="cont-test",
            panic_type=PanicType.SEGFAULT,
            message="segfault",
        )
        with pytest.raises(SecurityError) as raised:
            archive_incident(incident, base_dir=tmp_path)
        assert raised.value.error_code == "SECURITY_ERROR"


def test_archive_incident_atomic_replacement(tmp_path: Path) -> None:
    """Verify archive writes atomically and cleans up temporary file."""
    incident = PanicIncident(
        incident_id="incident-atomic-01",
        instance_id="inst-test",
        container_id="cont-test",
        panic_type=PanicType.GO_PANIC,
        message="test atomic",
    )
    dest = archive_incident(incident, base_dir=tmp_path)
    assert dest.exists()
    # Check no leftover tmp files
    tmp_files = list(tmp_path.glob(".tmp.*"))
    assert len(tmp_files) == 0


def test_a_panic_detected_while_the_archive_cannot_be_written_records_the_archive_error(
    tmp_path: Path,
) -> None:
    """A panic is still reported when its incident record cannot be archived, with the cause."""
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("a file where the archive directory should be", encoding="utf-8")

    incidents = detect_panics(
        ["Segmentation fault (core dumped)"],
        instance_id="inst-fail",
        container_id="cont-fail",
        archive=True,
        base_dir=blocker / "nested_dir",
    )

    assert [incident.panic_type for incident in incidents] == [PanicType.SEGFAULT]
    assert "Not a directory" in (incidents[0].archive_error or "")


def test_detect_single_line_crash_during_active_panic() -> None:
    """Verify single-line crash arriving during active multi-line panic emits both."""
    lines = [
        "panic: runtime error: invalid memory address",
        "goroutine 1 [running]:",
        "Segmentation fault",
        "main.main()",
    ]
    incidents = detect_panics(lines, instance_id="inst-combo", container_id="cont-combo")
    assert len(incidents) == 2
    types = [inc.panic_type for inc in incidents]
    assert PanicType.GO_PANIC in types
    assert PanicType.SEGFAULT in types


def test_detect_back_to_back_panics_message_isolation() -> None:
    """Verify back-to-back panic headers preserve respective panic messages."""
    lines = [
        "panic: first fatal crash",
        "goroutine 1 [running]:",
        "main.step1()",
        "panic: second fatal crash",
        "goroutine 2 [running]:",
        "main.step2()",
    ]
    incidents = detect_panics(lines, instance_id="inst-b2b", container_id="cont-b2b")
    assert len(incidents) == 2
    assert "first fatal crash" in incidents[0].message
    assert "second fatal crash" in incidents[1].message


def test_detect_rust_panic_symbolic_frames() -> None:
    """Verify Rust backtraces with standard symbol-based frames are collected."""
    lines = [
        "thread 'main' panicked at 'assertion failed', src/lib.rs:10:5",
        "stack backtrace:",
        "   0: std::panicking::begin_panic",
        "             at /rustc/library/std/src/panicking.rs:597:12",
        "   1: core::panicking::panic_fmt",
        "   2: myapp::calculate",
    ]
    incidents = detect_panics(lines, instance_id="inst-rust-sym", container_id="cont-rust-sym")
    assert len(incidents) == 1
    assert len(incidents[0].stacktrace) >= 4


def test_engine_logs_demux_stream_preservation(
    register_sandbox: Callable[..., SandboxInstance],
) -> None:
    """Verify each log line keeps the stream it was written to, in the engine's order (#2520)."""
    inst = register_sandbox(
        log_frames=[
            ("stdout", b"stdout log message\n"),
            ("stderr", b"stderr log message\n"),
            ("stdout", b"stdout again\n"),
        ]
    )

    report = WorkloadSandboxEngine().logs(identifier=inst.instance_id, detect_panics_flag=False)

    stamp = LOG_TIME.decode().strip()
    assert [(line.timestamp, line.stream, line.content) for line in report.lines] == [
        (stamp, "stdout", "stdout log message"),
        (stamp, "stderr", "stderr log message"),
        (stamp, "stdout", "stdout again"),
    ]


def test_engine_logs_follow_bounded_buffer(
    register_sandbox: Callable[..., SandboxInstance],
) -> None:
    """Verify follow mode bounds memory retention to MAX_FOLLOW_BUFFER_LINES."""
    inst = register_sandbox(log_frames=[("stdout", f"line {i}\n".encode()) for i in range(1500)])

    report = WorkloadSandboxEngine().logs(
        identifier=inst.instance_id, follow=True, tail="all", detect_panics_flag=False
    )

    assert (report.total_lines, len(report.lines), report.lines[-1].content) == (
        1500,
        MAX_FOLLOW_BUFFER_LINES,
        "line 1499",
    )


def test_cli_sandbox_logs_rich_escaping_and_secret_masking(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """Verify terminal log rendering escapes Rich markup and masks secrets."""
    inst = register_sandbox(
        log_frames=[
            (
                "stdout",
                b"Log with [bold red]untrusted tag[/bold red] and "
                b"ghp_token12345678901234567890123456\n",
            )
        ]
    )

    res = cli("sandbox", "logs", inst.instance_id)

    assert res.exit_code == 0
    assert "[bold red]untrusted tag[/bold red]" in res.stdout
    assert "<masked-github-token>" in res.stdout
    assert "ghp_token1234" not in res.stdout


def test_cli_sandbox_logs_json_masks_secrets(
    cli: Callable[..., Any], register_sandbox: Callable[..., SandboxInstance]
) -> None:
    """Verify --json output masks secrets in log lines and incident fields."""
    inst = register_sandbox(log_frames=[("stdout", b"API key sk-ant-secret12345678901234567890\n")])

    res = cli("sandbox", "logs", inst.instance_id, "--json")

    assert res.exit_code == 0
    assert "<masked-anthropic-key>" in res.stdout
    assert "sk-ant-secret" not in res.stdout


def test_cli_sandbox_logs_nonexistent_identifier_clean_exit(
    cli: Callable[..., Any], docker_daemon: DockerEngineFake
) -> None:
    """Verify explicit nonexistent identifier exits with status 1 and clean error message."""
    res = cli("sandbox", "logs", "nonexistent-id")

    assert (res.exit_code, res.output) == (
        1,
        "✗ Sandbox instance 'nonexistent-id' not found\n",
    )
