"""Tests for the keys that make a child write a file, which `build_subprocess_env` refuses (#2674)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_EXIT_FAILURE
from devops_cli.core.process import build_subprocess_env, run_subprocess
from devops_cli.exceptions import SecurityError

pytestmark = pytest.mark.live("python")

# Each key makes a child write a file that the caller names, so no caller can set one. A probe in
# a temporary HOME, with a scratch directory and a throwaway HTTPS server on the loopback address,
# made each child write its file. SSLKEYLOGFILE: curl 8.23.0, git 2.55.0 and the ssl module of
# Python 3.14 wrote the TLS secrets of the connection. QLOGDIR: curl wrote a QUIC log
# (`--http3-only`). NODE_V8_COVERAGE: Node.js v24.22.2 wrote a coverage file.
# NODE_REDIRECT_WARNINGS: Node.js wrote its warning to the file. LD_DEBUG_OUTPUT and
# LD_PROFILE_OUTPUT: the glibc 2.43 loader wrote its debug text and its profile, but only with the
# trigger keys LD_DEBUG and LD_PROFILE, so the guard refuses the whole LD_ family (ld.so(8)).
# PYTEST_ADDOPTS (#2747): pytest 9.1.1 with `--junitxml=<path>` wrote a JUnit file at the path.
# npm_config_logs_dir and npm_config_logs-dir (#2747): npm 11.19.1 and 10.9.9 wrote a debug log
# into the directory for `npm ls`.
REFUSED_FILE_WRITE_KEYS: tuple[str, ...] = (
    "SSLKEYLOGFILE",
    "QLOGDIR",
    "NODE_V8_COVERAGE",
    "NODE_REDIRECT_WARNINGS",
    "LD_DEBUG",
    "LD_DEBUG_OUTPUT",
    "LD_PROFILE",
    "LD_PROFILE_OUTPUT",
    "LD_BIND_NOW",
    "LD_EXAMPLE",
    "PYTEST_ADDOPTS",
    "npm_config_logs_dir",
    "npm_config_logs-dir",
)

ALL_CASES: tuple[str, ...] = (
    *REFUSED_FILE_WRITE_KEYS,
    *(k.lower() for k in REFUSED_FILE_WRITE_KEYS),
)


@pytest.mark.parametrize("isolate_env", [True, False], ids=["isolated", "not-isolated"])
@pytest.mark.parametrize("key", ALL_CASES)
def test_a_caller_override_that_makes_a_child_write_a_file_is_refused(
    key: str, isolate_env: bool
) -> None:
    """A caller override of a key that makes a child write a file that the caller names raises
    `SecurityError` that names the key, in upper and in lower case, with isolation on and off
    (#2674)."""
    with pytest.raises(SecurityError) as refused:
        build_subprocess_env(
            env={"EXAMPLE_FLAG": "on", key: "/opt/example/output"}, isolate_env=isolate_env
        )

    assert (refused.value.message, refused.value.exit_code, refused.value.error_code) == (
        f"Prohibited dangerous environment variable override: '{key}'",
        CONST_EXIT_FAILURE,
        "SECURITY_ERROR",
    )


def test_an_isolated_child_gets_no_file_write_key_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With isolation on, no key that makes a child write a file reaches the child from the
    environment of the person, in upper or in lower case (#2674)."""
    for key in ALL_CASES:
        monkeypatch.setenv(key, "example")

    env = build_subprocess_env(env={"EXAMPLE_FLAG": "on"})

    assert sorted(set(ALL_CASES) & set(env)) == []


@pytest.mark.parametrize("isolate_env", [True, False], ids=["isolated", "not-isolated"])
def test_a_key_that_only_contains_a_file_write_name_reaches_the_child(isolate_env: bool) -> None:
    """Keys that write no file reach the child with their values: the trust store keys of TLS and
    Node.js, keys that only contain a refused name, and keys with `LD_` inside (#2674)."""
    override = {
        "SSL_CERT_FILE": "/opt/example/ca.pem",
        "NODE_EXTRA_CA_CERTS": "/opt/example/ca.pem",
        "EXAMPLE_SSLKEYLOGFILE": "example",
        "QLOGDIR_EXAMPLE": "example",
        "NODE_V8_COVERAGE_EXAMPLE": "example",
        "BUILD_ID": "example",
        "OLD_LD_EXAMPLE": "example",
        "EXAMPLE_PYTEST_ADDOPTS": "example",
        "npm_config_logs_dirs": "example",
    }

    env = build_subprocess_env(env=override, isolate_env=isolate_env)

    assert {key: env.get(key) for key in override} == override


def test_a_child_without_isolation_gets_the_file_write_keys_of_the_person(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With isolation off, the child gets the environment of the person as it is,
    `SSLKEYLOGFILE` and `LD_DEBUG` included (#2674)."""
    monkeypatch.setenv("SSLKEYLOGFILE", "/opt/example/keys.log")
    monkeypatch.setenv("LD_DEBUG", "files")

    env = build_subprocess_env(isolate_env=False)

    assert (env["SSLKEYLOGFILE"], env["LD_DEBUG"]) == ("/opt/example/keys.log", "files")


def test_run_subprocess_starts_no_child_for_a_refused_file_write_key(tmp_path: Path) -> None:
    """`run_subprocess` raises `SecurityError` for a refused key before it starts the program, so
    the program writes no file (#2674)."""
    ran = tmp_path / "ran"
    program = [sys.executable, "-c", f"open({str(ran)!r}, 'w').close()"]

    with pytest.raises(SecurityError) as raised:
        run_subprocess(program, env={"SSLKEYLOGFILE": str(tmp_path / "keys.log")})
    assert raised.value.error_code == "SECURITY_ERROR"

    assert not ran.exists()
