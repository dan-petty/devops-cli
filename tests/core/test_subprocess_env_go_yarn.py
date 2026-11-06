"""Tests for the Go and Yarn keys that `build_subprocess_env` refuses or accepts (#2750)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_EXIT_FAILURE
from devops_cli.core.process import build_subprocess_env, run_subprocess
from devops_cli.exceptions import SecurityError

pytestmark = pytest.mark.live("python")

# Each key makes go or Yarn start a program that the caller names. A probe with go 1.24.7, in a
# temporary HOME with a marker program, ran the marker for each compile step of
# `GOFLAGS=-toolexec=<marker> go build .`; `go help build` documents `-toolexec`. Yarn 1.22.22
# ignored the key (it reads `yarn-path` from a `.yarnrc` file only). The bundle of Yarn 4.9.2
# reads the setting `yarnPath` from `YARN_YARN_PATH` and runs the file with `execFileSync`. No live
# run of Yarn 4 happened (the sandbox refused to run code that was downloaded from npm).
REFUSED_GO_YARN_KEYS: tuple[str, ...] = (
    "GOFLAGS",
    "YARN_YARN_PATH",
)


@pytest.mark.parametrize("isolate_env", [True, False], ids=["isolated", "not-isolated"])
@pytest.mark.parametrize(
    "key", [*REFUSED_GO_YARN_KEYS, *(key.lower() for key in REFUSED_GO_YARN_KEYS)]
)
def test_a_caller_override_that_makes_go_or_yarn_run_a_program_is_refused(
    key: str, isolate_env: bool
) -> None:
    """A caller override of a key that names a program of go or Yarn raises `SecurityError` that
    names the key, in upper and in lower case, with isolation on and off (#2750)."""
    with pytest.raises(SecurityError) as refused:
        build_subprocess_env(
            env={"EXAMPLE_FLAG": "on", key: "-toolexec=/opt/example/program"},
            isolate_env=isolate_env,
        )

    assert (refused.value.message, refused.value.exit_code, refused.value.error_code) == (
        f"Prohibited dangerous environment variable override: '{key}'",
        CONST_EXIT_FAILURE,
        "SECURITY_ERROR",
    )


def test_an_isolated_child_gets_no_go_or_yarn_program_key_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With isolation on, no allowed variable or prefix passes `GOFLAGS` or `YARN_YARN_PATH` from
    the environment of the person, in upper or in lower case. With isolation off, the child gets
    them as they are (#2750)."""
    environment_keys = [*REFUSED_GO_YARN_KEYS, *(key.lower() for key in REFUSED_GO_YARN_KEYS)]
    for key in environment_keys:
        monkeypatch.setenv(key, "example")

    isolated = build_subprocess_env(env={"EXAMPLE_FLAG": "on"})
    not_isolated = build_subprocess_env(isolate_env=False)

    assert (
        sorted(set(environment_keys) & set(isolated)),
        {"GOFLAGS", "YARN_YARN_PATH"} <= set(not_isolated),
    ) == ([], True)


@pytest.mark.parametrize("isolate_env", [True, False], ids=["isolated", "not-isolated"])
def test_a_key_that_only_contains_a_go_or_yarn_name_reaches_the_child(isolate_env: bool) -> None:
    """The refusal is an exact match: a key that only contains a refused name reaches the child
    with its value, as do the Go and Yarn keys that no probe made dangerous (#2750)."""
    override = {
        "EXAMPLE_GOFLAGS": "example",
        "GOFLAGS_EXAMPLE": "example",
        "EXAMPLE_YARN_YARN_PATH": "example",
        "YARN_ENABLE_TELEMETRY": "0",
    }

    env = build_subprocess_env(env=override, isolate_env=isolate_env)

    assert {key: env.get(key) for key in override} == override


def test_run_subprocess_starts_no_child_for_a_refused_go_key(tmp_path: Path) -> None:
    """`run_subprocess` raises `SecurityError` for a refused key before it starts the program, so
    the program runs nothing that the key names (#2750)."""
    ran = tmp_path / "ran"
    program = [sys.executable, "-c", f"open({str(ran)!r}, 'w').close()"]

    with pytest.raises(SecurityError) as raised:
        run_subprocess(program, env={"GOFLAGS": f"-toolexec={tmp_path / 'marker'}"})
    assert raised.value.error_code == "SECURITY_ERROR"

    assert not ran.exists()
