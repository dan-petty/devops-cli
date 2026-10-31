"""Tests for the gh and kubectl keys that `build_subprocess_env` refuses or accepts (#2672)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_EXIT_FAILURE
from devops_cli.core.process import build_subprocess_env, run_subprocess
from devops_cli.exceptions import SecurityError

pytestmark = pytest.mark.live("python")

# Each key names a program that gh or kubectl starts, so no caller can set one. A probe with gh
# 2.103.3 and kubectl 1.37.1, in a temporary HOME with a marker program, ran the marker for each
# key. gh starts the program of GH_BROWSER (`gh browse`), and BROWSER is its fall-back
# (`gh help environment`). gh starts the program of GH_EDITOR (`gh issue comment --editor`) and of
# GH_PAGER (`gh help reference`). `gh auth setup-git` writes the path of GH_PATH as the git
# credential helper, and git then starts it. kubectl starts the program of KUBE_EDITOR
# (`kubectl edit`) and of KUBECTL_EXTERNAL_DIFF (`kubectl diff`).
REFUSED_GH_KUBECTL_KEYS: tuple[str, ...] = (
    "GH_BROWSER",
    "BROWSER",
    "GH_EDITOR",
    "GH_PAGER",
    "GH_PATH",
    "KUBE_EDITOR",
    "KUBECTL_EXTERNAL_DIFF",
)


@pytest.mark.parametrize("isolate_env", [True, False], ids=["isolated", "not-isolated"])
@pytest.mark.parametrize(
    "key", [*REFUSED_GH_KUBECTL_KEYS, *(key.lower() for key in REFUSED_GH_KUBECTL_KEYS)]
)
def test_a_caller_override_that_makes_gh_or_kubectl_run_a_program_is_refused(
    key: str, isolate_env: bool
) -> None:
    """A caller override of a key that names a program of gh or kubectl raises `SecurityError`
    that names the key, in upper and in lower case, with isolation on and off (#2672)."""
    with pytest.raises(SecurityError) as refused:
        build_subprocess_env(
            env={"EXAMPLE_FLAG": "on", key: "/opt/example/program"}, isolate_env=isolate_env
        )

    assert (refused.value.message, refused.value.exit_code, refused.value.error_code) == (
        f"Prohibited dangerous environment variable override: '{key}'",
        CONST_EXIT_FAILURE,
        "SECURITY_ERROR",
    )


def test_an_isolated_child_gets_no_gh_or_kubectl_program_key_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With isolation on, no key that names a program of gh or kubectl reaches the child from the
    environment of the person, in upper or in lower case (#2672)."""
    environment_keys = [*REFUSED_GH_KUBECTL_KEYS, *(key.lower() for key in REFUSED_GH_KUBECTL_KEYS)]
    for key in environment_keys:
        monkeypatch.setenv(key, "example")

    env = build_subprocess_env(env={"EXAMPLE_FLAG": "on"})

    assert sorted(set(environment_keys) & set(env)) == []


@pytest.mark.parametrize("isolate_env", [True, False], ids=["isolated", "not-isolated"])
def test_a_gh_or_kubectl_key_that_names_a_file_or_a_value_reaches_the_child(
    isolate_env: bool, tmp_path: Path
) -> None:
    """The keys that callers set on purpose reach the child with their values: the directory of
    the gh configuration, the kubeconfig of the sandbox relay, the data directory of gh, and the
    token, host and repository of gh. So do keys that only contain a refused name (#2672)."""
    override = {
        "GH_CONFIG_DIR": str(tmp_path / "gh"),
        "KUBECONFIG": str(tmp_path / "kubeconfig.yaml"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "GH_TOKEN": "example-token",
        "GH_HOST": "example.com",
        "GH_REPO": "example/example",
        "GH_PROMPT_DISABLED": "1",
        "EXAMPLE_GH_BROWSER": "example",
        "EXAMPLE_KUBE_EDITOR": "example",
        "KUBECTL_EXTERNAL_DIFF_EXAMPLE": "example",
        "BROWSER_EXAMPLE": "example",
    }

    env = build_subprocess_env(env=override, isolate_env=isolate_env)

    assert {key: env.get(key) for key in override} == override


def test_a_child_without_isolation_gets_the_gh_and_kubectl_program_keys_of_the_person(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With isolation off, the child gets the environment of the person as it is, `GH_BROWSER`
    and `KUBE_EDITOR` included (#2672)."""
    monkeypatch.setenv("GH_BROWSER", "example-browser")
    monkeypatch.setenv("KUBE_EDITOR", "example-editor")

    env = build_subprocess_env(isolate_env=False)

    assert (env["GH_BROWSER"], env["KUBE_EDITOR"]) == ("example-browser", "example-editor")


def test_run_subprocess_starts_no_child_for_a_refused_gh_key(tmp_path: Path) -> None:
    """`run_subprocess` raises `SecurityError` for a refused key before it starts the program, so
    the program runs nothing that the key names (#2672)."""
    ran = tmp_path / "ran"
    program = [sys.executable, "-c", f"open({str(ran)!r}, 'w').close()"]

    with pytest.raises(SecurityError):
        run_subprocess(program, env={"GH_BROWSER": str(tmp_path / "browser")})

    assert not ran.exists()
