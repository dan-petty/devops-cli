"""Tests for the uv and npm keys that `build_subprocess_env` refuses or accepts (#2673)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_EXIT_FAILURE
from devops_cli.core.process import DEFAULT_ALLOWED_ENV_VARS, build_subprocess_env, run_subprocess
from devops_cli.exceptions import SecurityError

pytestmark = pytest.mark.live("python")

# Each key makes uv or npm start a program that the caller names. A probe with uv 0.13.6, npm
# 11.19.1 and node 24.22.2, in a temporary HOME with a marker program, ran the marker for each key.
# uv starts the interpreter of UV_PYTHON, and the `bin/python` of the environment that
# VIRTUAL_ENV or UV_PROJECT_ENVIRONMENT names. It starts an interpreter below UV_PYTHON_INSTALL_DIR
# when it prefers its own Python builds (UV_MANAGED_PYTHON=1). npm starts the shell of
# `script-shell` for each script, and `node-options` becomes NODE_OPTIONS for each script. npm
# starts the program of `git` for a git dependency, the program of `editor` for `npm config edit`,
# and loads the module of `init-module` for `npm init`.
REFUSED_UV_NPM_KEYS: tuple[str, ...] = (
    "UV_PYTHON",
    "UV_PYTHON_INSTALL_DIR",
    "UV_PROJECT_ENVIRONMENT",
    "VIRTUAL_ENV",
    "npm_config_script_shell",
    "npm_config_node_options",
    "npm_config_git",
    "npm_config_editor",
    "npm_config_init_module",
)

# npm reads an environment key such as `npm_config_script-shell` as the same setting as
# `npm_config_script_shell`: the probe ran the marker for each spelling below.
REFUSED_NPM_HYPHEN_KEYS: tuple[str, ...] = (
    "npm_config_script-shell",
    "npm_config_node-options",
    "npm_config_init-module",
)

ALL_REFUSED_KEYS: tuple[str, ...] = (*REFUSED_UV_NPM_KEYS, *REFUSED_NPM_HYPHEN_KEYS)


def _spellings(keys: tuple[str, ...]) -> list[str]:
    """Each key as given, in upper case and in lower case."""
    return sorted({*keys, *(key.upper() for key in keys), *(key.lower() for key in keys)})


@pytest.mark.parametrize("isolate_env", [True, False], ids=["isolated", "not-isolated"])
@pytest.mark.parametrize("key", _spellings(ALL_REFUSED_KEYS))
def test_a_caller_override_that_makes_uv_or_npm_run_a_program_is_refused(
    key: str, isolate_env: bool
) -> None:
    """A caller override of a key that names a program of uv or npm raises `SecurityError` that
    names the key, in each spelling, with isolation on and off (#2673)."""
    with pytest.raises(SecurityError) as refused:
        build_subprocess_env(
            env={"EXAMPLE_FLAG": "on", key: "/opt/example/program"}, isolate_env=isolate_env
        )

    assert (refused.value.message, refused.value.exit_code, refused.value.error_code) == (
        f"Prohibited dangerous environment variable override: '{key}'",
        CONST_EXIT_FAILURE,
        "SECURITY_ERROR",
    )


def test_an_isolated_child_gets_no_virtual_env_or_npm_program_key_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With isolation on, no npm key that names a program and no `VIRTUAL_ENV` reaches the child
    from the environment of the person, in any spelling (#2673)."""
    environment_keys = [
        key
        for key in _spellings(ALL_REFUSED_KEYS)
        if not key.upper().startswith("UV_") and key.upper() != "VIRTUAL_ENV"
    ] + ["VIRTUAL_ENV", "virtual_env"]
    for key in environment_keys:
        monkeypatch.setenv(key, "example")

    env = build_subprocess_env(env={"EXAMPLE_FLAG": "on"})

    assert sorted(set(environment_keys) & set(env)) == []


def test_virtual_env_is_not_in_the_ambient_allowlist() -> None:
    """`VIRTUAL_ENV` names the environment whose `bin/python` uv starts. No child of devops-cli
    reads it: the `uv` calls name their interpreter or use the project environment (#2673)."""
    assert "VIRTUAL_ENV" not in DEFAULT_ALLOWED_ENV_VARS


def test_a_child_without_isolation_gets_the_uv_and_npm_program_keys_of_the_person(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With isolation off, the child gets the environment of the person as it is (#2673)."""
    monkeypatch.setenv("VIRTUAL_ENV", "/example/venv")
    monkeypatch.setenv("npm_config_script_shell", "/example/shell")

    env = build_subprocess_env(isolate_env=False)

    assert (env["VIRTUAL_ENV"], env["npm_config_script_shell"]) == (
        "/example/venv",
        "/example/shell",
    )


def test_an_isolated_child_gets_the_uv_settings_of_the_person(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `UV_` prefix of the ambient allowlist keeps passing the uv settings of the person to an
    isolated child, the three program keys included. A `uv run` of the gate on a CI runner needs
    `UV_PYTHON` and `UV_PYTHON_INSTALL_DIR` to keep the interpreter that `uv sync` built (#1735).
    The environment of the person is as trusted as `PATH`, which also decides what a child starts
    (#2673)."""
    uv_keys = {
        "UV_PYTHON": "3.14",
        "UV_PYTHON_INSTALL_DIR": "/runner/example/python",
        "UV_PROJECT_ENVIRONMENT": "/runner/example/venv",
        "UV_CACHE_DIR": "/runner/example/cache",
    }
    for key, value in uv_keys.items():
        monkeypatch.setenv(key, value)

    env = build_subprocess_env()

    assert {key: env.get(key) for key in uv_keys} == uv_keys


@pytest.mark.parametrize("isolate_env", [True, False], ids=["isolated", "not-isolated"])
def test_a_uv_or_npm_key_that_names_no_program_reaches_the_child(
    isolate_env: bool, tmp_path: Path
) -> None:
    """The keys that callers set on purpose reach the child with their values: the npm settings of
    `devops install-tools` and the uv settings that it names. So do the file keys that a probe
    showed can name a program (`npm_config_userconfig` with an npmrc, `UV_CONFIG_FILE`), because
    a caller names a file that it controls, as for `GH_CONFIG_DIR` (#2672). So do keys that only
    contain a refused name (#2673)."""
    override = {
        "npm_config_cache": str(tmp_path / "cache"),
        "npm_config_userconfig": str(tmp_path / "npmrc"),
        "npm_config_globalconfig": str(tmp_path / "global-npmrc"),
        "npm_config_update_notifier": "false",
        "npm_config_loglevel": "error",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
        "UV_LINK_MODE": "copy",
        "UV_MALWARE_CHECK": "1",
        "UV_CONFIG_FILE": str(tmp_path / "uv.toml"),
        "UV_PYTHON_DOWNLOADS": "never",
        "npm_config_git_tag_version": "false",
        "npm_config_script_shell_example": "example",
        "NPM_CONFIG_GITHUB": "example",
        "EXAMPLE_UV_PYTHON": "example",
        "UV_PYTHON_EXAMPLE": "example",
        "EXAMPLE_VIRTUAL_ENV": "example",
        "VIRTUAL_ENV_EXAMPLE": "example",
    }

    env = build_subprocess_env(env=override, isolate_env=isolate_env)

    assert {key: env.get(key) for key in override} == override


def test_run_subprocess_starts_no_child_for_a_refused_uv_key(tmp_path: Path) -> None:
    """`run_subprocess` raises `SecurityError` for a refused key before it starts the program, so
    the program runs nothing that the key names (#2673)."""
    ran = tmp_path / "ran"
    program = [sys.executable, "-c", f"open({str(ran)!r}, 'w').close()"]

    with pytest.raises(SecurityError):
        run_subprocess(program, env={"UV_PYTHON": str(tmp_path / "python")})

    assert not ran.exists()
