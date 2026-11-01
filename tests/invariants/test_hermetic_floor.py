"""Hermetic floor invariants: default deny of process, network, and keyring edges, telemetry-off
default, per-test process-wide state resets, and shared `config` and `cli` fixtures (#1310)."""

from __future__ import annotations

import ast
import os
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config import os_keyring
from devops_cli.config.settings import load_settings
from devops_cli.telemetry.tracer import get_tracer
from tests.support.fakes.keyring import FakeKeyring
from tests.support.paths import REPO_ROOT


def _run_with_floor(
    pytester: pytest.Pytester,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> pytest.RunResult:
    """Run `source` inside `pytester` with the root conftest floor loaded in-process."""
    home = os.environ.get("HOME", str(pytester.path))
    monkeypatch.setenv("HOME", home)
    pytester.makepyfile(test_inner=source)
    return pytester.runpytest(
        "-p",
        "tests.conftest",
        "-p",
        "no:randomly",
        "-p",
        "no:logfire",
        "-p",
        "no:pytest_logfire",
        "-o",
        f"pythonpath={REPO_ROOT}",
        "-o",
        "asyncio_default_fixture_loop_scope=function",
    )


def test_uncaught_and_caught_process_reaches_fail_with_edge_name(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A test that starts a non-exempt process without a fake fails naming the process edge,
    both when the error propagates and when the code under test catches `Exception`."""
    result = _run_with_floor(
        pytester,
        monkeypatch,
        """
        import subprocess

        def test_uncaught():
            subprocess.run(["gh", "api", "user"])

        def test_caught():
            try:
                subprocess.run(["gh", "api", "user"])
            except Exception:
                pass
        """,
    )
    result.assert_outcomes(failed=2, errors=2)
    output = result.stdout.str()
    assert "process edge reached without a fake: gh api user" in output


def test_live_marker_allows_installed_binary_and_skips_missing_binary(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`@pytest.mark.live` allows an installed local tool and skips when the tool is missing."""
    result = _run_with_floor(
        pytester,
        monkeypatch,
        """
        import subprocess
        import pytest

        @pytest.mark.live("echo")
        def test_present_live_tool():
            completed = subprocess.run(["echo", "ready"], capture_output=True, text=True, check=True)
            assert completed.stdout.strip() == "ready"

        @pytest.mark.live("nonexistent_binary_1310")
        def test_missing_live_tool():
            subprocess.run(["nonexistent_binary_1310"])
        """,
    )
    result.assert_outcomes(passed=1, skipped=1)


def test_the_floor_refuses_bubblewrap_in_a_test_without_the_bwrap_mark(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A review runs its tools in the sandbox by default (#2096). There a real tool starts as the
    program that bubblewrap confines, and a refusal of the tool by its name does not see it. So
    bubblewrap starts only in a test with the `bwrap` mark. The floor refuses the start before
    the program runs, so the case is the same on a host with bubblewrap and on one without it.
    The `bwrap` tests themselves show that the mark lets bubblewrap start."""
    result = _run_with_floor(
        pytester,
        monkeypatch,
        """
        import subprocess

        def test_unmarked():
            subprocess.run(["bwrap", "--version"])
        """,
    )
    assert "process edge reached without a fake: bwrap --version" in result.stdout.str()
    assert result.parseoutcomes().get("passed", 0) == 0


def test_uncaught_and_caught_network_reaches_fail_with_edge_name(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """External connects, unowned loopback ports, unowned AF_UNIX sockets, and external DNS
    lookups fail naming the network edge even when caught by `except Exception:`."""
    result = _run_with_floor(
        pytester,
        monkeypatch,
        """
        import socket

        def test_external_connect_caught():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect(("93.184.215.14", 443))
            except Exception:
                pass
            finally:
                sock.close()

        def test_unowned_loopback_caught():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect(("127.0.0.1", 6379))
            except Exception:
                pass
            finally:
                sock.close()

        def test_unowned_unix_socket_caught(tmp_path):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.connect(str(tmp_path / "unowned.sock"))
            except Exception:
                pass
            finally:
                sock.close()

        def test_external_dns_caught():
            try:
                socket.getaddrinfo("example.com", 443)
            except Exception:
                pass
        """,
    )
    result.assert_outcomes(passed=4, errors=4)
    output = result.stdout.str()
    assert "network edge reached without a fake" in output
    assert "93.184.215.14:443" in output
    assert "127.0.0.1:6379" in output
    assert "unowned.sock" in output
    assert "dns:example.com" in output


def test_unreachable_marker_refuses_endpoint_without_failing_teardown(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`@pytest.mark.unreachable` refuses the named endpoint or hostname without failing the test."""
    result = _run_with_floor(
        pytester,
        monkeypatch,
        """
        import socket
        import pytest

        @pytest.mark.unreachable("127.0.0.1:6379", "example.com")
        def test_unreachable_targets_refused_cleanly():
            with pytest.raises(ConnectionRefusedError):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.connect(("127.0.0.1", 6379))
                finally:
                    sock.close()
            with pytest.raises(socket.gaierror):
                socket.getaddrinfo("example.com", 443)
        """,
    )
    result.assert_outcomes(passed=1)


def test_in_process_tcp_and_unix_servers_pass(tmp_path: Path) -> None:
    """A connect to a loopback port or AF_UNIX socket that the test itself listens on passes."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=1.0) as client:
            accepted, _ = server.accept()
            with accepted:
                client.sendall(b"ping")
                assert accepted.recv(4) == b"ping"

    unix_path = str(tmp_path / "s.sock")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as unix_server:
        unix_server.bind(unix_path)
        unix_server.listen(1)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as unix_client:
            unix_client.connect(unix_path)
            accepted, _ = unix_server.accept()
            with accepted:
                unix_client.sendall(b"pong")
                assert accepted.recv(4) == b"pong"


def test_uncaught_and_caught_keyring_reaches_fail_and_fake_restores_deny(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A keyring or D-Bus reach through the keyring seam without a fake fails naming the keyring
    edge even when caught, `keyring_store` in one test leaves the deny edge for the next, and
    code that calls the `keyring` library itself meets the deny backend."""
    result = _run_with_floor(
        pytester,
        monkeypatch,
        """
        import keyring
        from devops_cli.config import os_keyring

        def test_with_fake_keyring(keyring_store):
            os_keyring.keyring_write("token", "secret-val")
            assert os_keyring.keyring_read("token") == "secret-val"

        def test_after_fake_keyring_is_denied_again():
            os_keyring.keyring_read("token")

        def test_caught_bus_reach_fails_teardown():
            try:
                os_keyring.session_bus_running(__import__("pathlib").Path("bus"))
            except Exception:
                pass

        def test_caught_library_reach_fails_teardown():
            try:
                keyring.set_password("devops-cli", "token", "secret-val")
            except Exception:
                pass
        """,
    )
    result.assert_outcomes(passed=3, failed=1, errors=3)
    output = result.stdout.str()
    assert (
        "keyring edge reached without a fake: devops-cli/token" in output,
        "keyring edge reached without a fake: session-bus/bus" in output,
    ) == (True, True)


def test_keyring_store_installs_an_isolated_fake(keyring_store: FakeKeyring) -> None:
    """`keyring_store` installs an empty in-memory `FakeKeyring` through the keyring seam."""
    os_keyring.keyring_write("user", "value")

    assert (os_keyring.keyring_read("user"), keyring_store.values) == ("value", {"user": "value"})


def test_telemetry_is_off_by_default_and_opts_in_through_config(
    config: Callable[..., Path],
) -> None:
    """The floor turns telemetry export off by default; a test opts in through `config`."""
    assert load_settings().telemetry.enabled is False
    assert get_tracer().enabled is False

    config(telemetry={"enabled": True, "service_name": "floor-test"})
    assert load_settings().telemetry.enabled is True
    assert get_tracer().enabled is True


def test_config_writes_overrides_and_isolates_tests(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`config` writes overrides into the per-test `config.yaml` and resets the settings cache,
    and two tests do not see each other's overrides."""
    result = _run_with_floor(
        pytester,
        monkeypatch,
        """
        from devops_cli.config.settings import load_settings

        def test_first_override(config):
            config(github={"default_org": "first-org"})
            assert load_settings().github.default_org == "first-org"

        def test_second_does_not_see_first_override(config):
            assert load_settings().github.default_org != "first-org"
            config({"github": {"default_org": "second-org"}})
            assert load_settings().github.default_org == "second-org"
        """,
    )
    result.assert_outcomes(passed=2)


def test_process_wide_state_resets_between_tests(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Process-wide state mutated in one test is reset by the floor before the next test runs."""
    result = _run_with_floor(
        pytester,
        monkeypatch,
        """
        from devops_cli.dry_run.state import is_dry_run, set_dry_run

        def test_mutate_state():
            set_dry_run(True)
            assert is_dry_run() is True

        def test_state_was_reset():
            assert is_dry_run() is False
        """,
    )
    result.assert_outcomes(passed=2)


def test_a_dispatch_worker_abandoned_by_a_timeout_is_finished_before_the_next_test_starts(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dispatch that passes its timeout leaves its worker running. The floor waits for that
    worker while the test's isolation holds: a worker that finishes later reads the real
    settings, builds an enabled tracer, and exports to port 4318 during another test (#2277)."""
    result = _run_with_floor(
        pytester,
        monkeypatch,
        """
        import threading
        import time

        from devops_cli.ai.mcp.dispatcher import InProcessDispatcher
        from devops_cli.main import app

        finished = []

        def test_the_dispatch_times_out_and_the_command_is_released(monkeypatch):
            release = threading.Event()

            def slow_success(span, cmd_name, labels, seconds):
                time.sleep(0.5)
                finished.append(cmd_name)

            monkeypatch.setattr("devops_cli.core.cli._record_cli_success", slow_success)

            @app.command(name="_hang_2277", hidden=True)
            def _hang():
                release.wait(10)

            try:
                code, _ = InProcessDispatcher().dispatch(["devops", "_hang_2277"], timeout=0.1)
                assert code == 124
            finally:
                release.set()
                app.registered_commands = [
                    c for c in app.registered_commands if c.name != "_hang_2277"
                ]

        def test_the_worker_finished_before_this_test_started():
            assert finished == ["_hang_2277"]
        """,
    )
    result.assert_outcomes(passed=2)


def test_cli_fixture_runs_app_in_process_with_stdin(cli: Callable[..., Any]) -> None:
    """`cli` invokes `devops <args>` in-process with the floor's terminal settings and `input=`."""
    version_result = cli("--version")
    assert version_result.exit_code == 0
    assert "devops" in version_result.stdout.lower()

    help_result = cli(["--help"], input="ignored\n")
    assert help_result.exit_code == 0
    assert "Usage:" in help_result.stdout


def _tree(root: Path) -> dict[str, str | None]:
    """Each path under `root`, relative, with a file's text, or None for a directory."""
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        if path.is_file()
        else None
        for path in sorted(root.rglob("*"))
    }


def test_a_config_write_outside_the_run_fails_at_the_write_naming_the_test(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A test that opens a config file for writing, renames a file onto one or removes one
    outside its run's temporary directory fails at that operation, naming itself, also when it
    catches the failure, and so does a `save_settings` of a changed key without isolation. The
    file stays as it was.
    A config file under `tmp_path` and another file outside stay writable (#1921).

    The files outside the inner run lie in this test's own temporary directory, so a guard that
    lets a write through changes nothing a person keeps."""
    outside = pytester.path / "outside"
    (outside / "kept").mkdir(parents=True)
    (outside / "kept" / "config.yaml").write_text("ssh:\n  key_prefix: kept\n", encoding="utf-8")
    (outside / "checkout" / ".git").mkdir(parents=True)
    checkout_config = "ssh:\n  key_prefix: devops_cli\n"
    (outside / "checkout" / "config.yaml").write_text(checkout_config, encoding="utf-8")
    before = _tree(outside)
    result = _run_with_floor(
        pytester,
        monkeypatch,
        f"""
        import os
        from pathlib import Path

        from devops_cli.config.settings import load_settings, save_settings

        OUTSIDE = Path({str(outside)!r})

        def test_opens_for_writing():
            (OUTSIDE / "config.yaml").write_text("ssh: null\\n", encoding="utf-8")

        def test_renames_onto(tmp_path):
            staged = tmp_path / "staged.yaml"
            staged.write_text("ssh: null\\n", encoding="utf-8")
            os.replace(staged, OUTSIDE / ".devops.yaml")

        def test_removes():
            os.remove(OUTSIDE / "kept" / "config.yaml")

        def test_catches_the_failure():
            try:
                (OUTSIDE / "kept" / "config.yaml").write_text("ssh: null\\n", encoding="utf-8")
            except Exception:
                pass

        def test_saves_settings_without_isolation(monkeypatch):
            monkeypatch.delenv("DEVOPS_CLI_CONFIG")
            monkeypatch.chdir(OUTSIDE / "checkout")
            settings = load_settings()
            settings.ssh.key_prefix = "changed"
            save_settings(settings)

        def test_writes_a_config_file_under_tmp_path(tmp_path):
            (tmp_path / "config.yaml").write_text("ssh: null\\n", encoding="utf-8")

        def test_writes_another_file_outside():
            (OUTSIDE / "notes.txt").write_text("notes\\n", encoding="utf-8")
        """,
    )
    result.assert_outcomes(passed=2, failed=5, errors=5)
    output = result.stdout.str()
    refused = [line for line in output.splitlines() if "config write outside the run's" in line]
    failing = {
        "test_opens_for_writing",
        "test_renames_onto",
        "test_removes",
        "test_catches_the_failure",
        "test_saves_settings_without_isolation",
    }
    named = {test for test in failing for line in refused if f"::{test} (call)" in line}
    assert named == failing
    assert _tree(outside) == {**before, "notes.txt": "notes\n"}


def test_a_spend_ledger_write_outside_the_run_fails_at_the_write_naming_the_test(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A test that opens a spend ledger for writing outside its run's temporary directory
    fails at that operation, naming itself, also when it catches the failure, and so does
    a SpendLedger instantiation pointing outside. A spend ledger under tmp_path stays
    writable (#2192)."""
    outside = pytester.path / "outside"
    outside.mkdir(parents=True)
    result = _run_with_floor(
        pytester,
        monkeypatch,
        f"""
        import os
        import sqlite3
        from pathlib import Path

        from devops_cli.ai.spend.ledger import SpendLedger

        OUTSIDE = Path({str(outside)!r})

        def test_opens_spend_ledger_for_writing():
            SpendLedger(OUTSIDE / "spend.db")

        def test_direct_sqlite3_connect_outside():
            sqlite3.connect(str(OUTSIDE / "spend.db"))

        def test_direct_file_write_outside():
            (OUTSIDE / "spend.db").write_text("corrupted\\n", encoding="utf-8")

        def test_catches_the_failure():
            try:
                SpendLedger(OUTSIDE / "spend.db")
            except Exception:
                pass

        def test_writes_spend_ledger_under_tmp_path(tmp_path):
            SpendLedger(tmp_path / "spend.db")

        def test_writes_another_db_outside():
            conn = sqlite3.connect(str(OUTSIDE / "other.db"))
            conn.close()
        """,
    )
    result.assert_outcomes(passed=2, failed=4, errors=4)
    output = result.stdout.str()
    refused = [
        line for line in output.splitlines() if "spend ledger write outside the run's" in line
    ]
    failing = {
        "test_opens_spend_ledger_for_writing",
        "test_direct_sqlite3_connect_outside",
        "test_direct_file_write_outside",
        "test_catches_the_failure",
    }
    named = {test for test in failing for line in refused if f"::{test} (call)" in line}
    assert named == failing


def test_test_modules_repeat_no_floor_resets() -> None:
    """None of the 15 autouse fixtures repeating floor resets remain in test modules (#2173)."""
    import ast

    target_fixtures = {
        ("tests/k8s/test_k8s_service_proxy.py", "clear_configuration_cache"),
        ("tests/security/test_secret_resolution.py", "_reset_resolver_singleton"),
        ("tests/telemetry/test_telemetry_logfire.py", "_clean_logfire_state"),
        ("tests/ai/rag/test_rag_kb_sync.py", "clean_kb_sync_state"),
        ("tests/core/test_gitignore_evaluation.py", "clear_indexes"),
        ("tests/ai/client/test_ai_request_priority.py", "_clean_state"),
        ("tests/k8s/test_k8s_service.py", "reset_k8s_service"),
        ("tests/ai/client/test_ollama_dynamic_leasing.py", "_reset_slots"),
        ("tests/ai/mcp/test_fastmcp_contracts.py", "reset_domain_gate"),
        ("tests/k8s/test_k8s_context_resolution.py", "clear_context_cache"),
        ("tests/commands/test_config_field_validation.py", "_reset_cache"),
        ("tests/ai/rag/test_rag_investigator.py", "_reset_investigation_cache"),
        ("tests/commands/test_ci_dry_run.py", "reset_dry_run_state"),
        ("tests/dry_run/test_consolidation_dry_run_decorator.py", "reset_dry_run_state"),
        ("tests/commands/test_review_rules_pack.py", "_reset_dry_run"),
    }

    found: list[str] = []
    for rel_path, fixture_name in target_fixtures:
        full_path = REPO_ROOT / rel_path
        if not full_path.exists():
            continue
        try:
            tree = ast.parse(full_path.read_text(encoding="utf-8"), filename=str(full_path))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == fixture_name:
                found.append(f"{rel_path}:{fixture_name}")

    assert not found, f"Autouse floor reset fixtures still present: {found}"


def _is_fixture_def(node: ast.AST) -> bool:
    if not isinstance(node, ast.FunctionDef):
        return False
    return any(
        (isinstance(d, ast.Name) and d.id == "fixture")
        or (isinstance(d, ast.Attribute) and d.attr == "fixture")
        or (
            isinstance(d, ast.Call)
            and isinstance(d.func, (ast.Name, ast.Attribute))
            and (
                getattr(d.func, "id", None) == "fixture"
                or getattr(d.func, "attr", None) == "fixture"
            )
        )
        for d in node.decorator_list
    )


def test_project_and_tree_fixtures_are_distinct() -> None:
    """The project and tree fixtures must not be defined under identical names across test modules (#2173)."""
    project_defs: list[str] = []
    tree_defs: list[str] = []
    tests_root = REPO_ROOT / "tests"

    for path in sorted(tests_root.rglob("*.py")):
        if "support" in path.parts or path.name == "conftest.py":
            continue
        try:
            tree_ast = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception:
            continue
        for node in ast.walk(tree_ast):
            if not _is_fixture_def(node):
                continue
            assert isinstance(node, ast.FunctionDef)
            if node.name == "project":
                project_defs.append(str(path.relative_to(REPO_ROOT)))
            elif node.name == "tree":
                tree_defs.append(str(path.relative_to(REPO_ROOT)))

    assert len(project_defs) <= 1, f"Multiple 'project' fixtures found: {project_defs}"
    assert len(tree_defs) <= 1, f"Multiple 'tree' fixtures found: {tree_defs}"


def test_dead_test_helper_files_are_deleted() -> None:
    """The five test files that test test helpers or conftest rather than src/ are deleted (#2173)."""
    dead_files = [
        "tests/ai/client/test_model_fixture.py",
        "tests/core/test_support_waits.py",
        "tests/core/test_support_hung_children.py",
        "tests/config/test_per_test_timeout.py",
        "tests/core/test_openblas_worker_threads.py",
    ]
    existing = [f for f in dead_files if (REPO_ROOT / f).exists()]
    assert not existing, f"Dead test helper files still exist: {existing}"


def test_test_settings_ci_row_registered() -> None:
    """The test-settings check spec is registered in get_check_specs() (#2173)."""
    from devops_cli.commands.ci import get_check_spec, get_check_specs

    spec_names = {s.name for s in get_check_specs()}
    assert "test-settings" in spec_names, "test-settings row missing from get_check_specs()"
    spec = get_check_spec("test-settings")
    assert "check_test_settings" in " ".join(spec.cmd)
