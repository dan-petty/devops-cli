"""Verify what the `devops config` commands tell the user about the config file they write."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.settings import reset_settings_cache
from devops_cli.exceptions import ConfigurationError
from tests.support.config_writes import written_keys
from tests.support.fakes.clock import ClockFake

_REMOVED_LINE = "  vllm_url: http://192.0.2.10:8000\n"
_WITH_REMOVED_KEY = (
    "# devops-cli settings of this workstation\n"
    "telemetry:\n"
    "  enabled: false\n"
    "ai:\n"
    "  # The provider of every task.\n"
    "  provider: ollama\n"
    f"{_REMOVED_LINE}"
)


def _use(config_path: Path, text: str) -> None:
    """Make `text` the content of the active config file."""
    config_path.write_text(text, encoding="utf-8")
    reset_settings_cache()


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def test_config_init_names_the_active_config_file_it_writes(
    cli: Any, config: Any, tmp_path: Path, isolate_data_dir: Path
) -> None:
    """The wizard wrote the active config file but named the default config path (#1998). It
    writes only the keys that the answers change (#1999).

    The floor's `DEVOPS_CLI_CONFIG` makes a file under `tmp_path` the active config. An empty
    PATH holds no gh, so the wizard asks no gh question and starts no program.
    """
    active = config(github={"default_org": "old-org"})
    no_programs = tmp_path / "no-programs"
    no_programs.mkdir()
    answers = f"new-org\n{tmp_path / 'repos'}\n\n\n\n"

    result = cli("config", "init", input=answers, env={"PATH": str(no_programs)})

    named = [line for line in result.output.splitlines() if line.startswith("Config file:")]
    written = yaml.safe_load(active.read_text(encoding="utf-8"))["github"]["default_org"]
    assert (result.exit_code, named, written, written_keys(isolate_data_dir)) == (
        0,
        [f"Config file: {active}"],
        "new-org",
        [["github.default_org", "repos.base_dir"]],
    )


def test_config_unset_removes_a_key_that_stops_every_command_from_loading_the_settings(
    cli: Any, isolate_devops_cli_config: Path, clock: ClockFake
) -> None:
    """`ai.vllm_url` stops `devops config get` from loading the settings. `devops config unset`
    does not load them: it removes the line of the key, keeps the comments and copies the file."""
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)
    clock.move_to(datetime(2026, 10, 24, 23, 30, 5, tzinfo=UTC))
    backup = isolate_devops_cli_config.with_name("config.yaml.bak-20261024-233005")

    refused = cli("config", "get", "ai.provider")
    result = cli("config", "unset", "ai.vllm_url")
    loaded = cli("config", "get", "ai.provider")

    assert (refused.exit_code, type(refused.exception)) == (1, ConfigurationError)
    assert (result.exit_code, result.output) == (
        0,
        f"Removed ai.vllm_url from {isolate_devops_cli_config}:7.\n"
        f"The file before the change is in {backup}.\n",
    )
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_REMOVED_KEY.replace(
        _REMOVED_LINE, ""
    )
    assert backup.read_text(encoding="utf-8") == _WITH_REMOVED_KEY
    assert (loaded.exit_code, loaded.output) == (0, "ollama\n")


def test_config_unset_of_a_key_that_the_file_does_not_hold_exits_1_and_changes_nothing(
    cli: Any, isolate_devops_cli_config: Path
) -> None:
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)

    result = cli("config", "unset", "ai.no_such_key")

    assert (result.exit_code, result.output) == (
        1,
        f"✗ The config file {isolate_devops_cli_config} does not hold the key "
        "'ai.no_such_key'. Nothing changed.\n",
    )
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_REMOVED_KEY
    assert _names(isolate_devops_cli_config.parent) == ["config.yaml"]


def test_config_unset_dry_run_prints_the_change_and_writes_nothing(
    cli: Any, isolate_devops_cli_config: Path, isolate_data_dir: Path
) -> None:
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)

    result = cli("config", "unset", "ai.vllm_url", "--dry-run")

    assert (result.exit_code, json.loads(result.output.split("Command response:\n")[1])) == (
        0,
        {
            "command": "devops config unset",
            "target": str(isolate_devops_cli_config),
            "dry_run": True,
            "status": "DRY_RUN",
            "action": "remove_config_key",
            "details": {
                "key": "ai.vllm_url",
                "line": 7,
                "diff": [
                    f"--- {isolate_devops_cli_config}",
                    f"+++ {isolate_devops_cli_config}",
                    "@@ -7 +6,0 @@",
                    f"-{_REMOVED_LINE.rstrip()}",
                ],
            },
        },
    )
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_REMOVED_KEY
    assert _names(isolate_devops_cli_config.parent) == ["config.yaml"]
    assert written_keys(isolate_data_dir) == []


def test_the_unset_command_that_the_error_names_for_the_other_config_file_removes_the_key(
    cli: Any, tmp_path: Path
) -> None:
    """For a key in a config file that is not the active one, the error names the command with
    `DEVOPS_CLI_CONFIG` set to that file."""
    other = tmp_path / "global" / "config.yaml"
    other.parent.mkdir()
    other.write_text("github:\n  default_org: example-org\nai:\n  vllm_url: x\n", encoding="utf-8")

    result = cli("config", "unset", "ai.vllm_url", env={"DEVOPS_CLI_CONFIG": str(other)})

    assert (result.exit_code, other.read_text(encoding="utf-8")) == (
        0,
        "github:\n  default_org: example-org\nai: {}\n",
    )
