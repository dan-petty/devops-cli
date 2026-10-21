"""Hermetic floor invariants: default deny of process, network, and keyring edges, telemetry-off
default, per-test process-wide state resets, and shared `config` and `cli` fixtures (#1310)."""

from __future__ import annotations

import os
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

import keyring
import pytest

from devops_cli.config.settings import load_settings
from devops_cli.telemetry.tracer import get_tracer
from tests.cluster_secret_fakes import FakeKeyring
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
    """Calling keyring without a fake fails naming the keyring edge even when caught, and
    installing `FakeKeyring` in one test restores the deny backend for the next test."""
    result = _run_with_floor(
        pytester,
        monkeypatch,
        """
        import keyring
        from tests.cluster_secret_fakes import FakeKeyring

        def test_with_fake_keyring():
            keyring.set_keyring(FakeKeyring())
            keyring.set_password("devops-cli", "token", "secret-val")
            assert keyring.get_password("devops-cli", "token") == "secret-val"

        def test_after_fake_keyring_is_denied_again():
            keyring.get_password("devops-cli", "token")

        def test_caught_keyring_reach_fails_teardown():
            try:
                keyring.set_password("devops-cli", "token", "secret-val")
            except Exception:
                pass
        """,
    )
    result.assert_outcomes(passed=2, failed=1, errors=2)
    output = result.stdout.str()
    assert "keyring edge reached without a fake: devops-cli/token" in output


def test_mock_keyring_fixture_installs_isolated_fake(mock_keyring: FakeKeyring) -> None:
    """`mock_keyring` installs an in-memory `FakeKeyring` for the test."""
    keyring.set_password("devops-cli", "user", "value")
    assert keyring.get_password("devops-cli", "user") == "value"
    assert mock_keyring.get_password("devops-cli", "user") == "value"


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


def test_cli_fixture_runs_app_in_process_with_stdin(cli: Callable[..., Any]) -> None:
    """`cli` invokes `devops <args>` in-process with the floor's terminal settings and `input=`."""
    version_result = cli("--version")
    assert version_result.exit_code == 0
    assert "devops" in version_result.stdout.lower()

    help_result = cli(["--help"], input="ignored\n")
    assert help_result.exit_code == 0
    assert "Usage:" in help_result.stdout
