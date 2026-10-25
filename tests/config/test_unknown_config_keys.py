"""A config file key that a settings section refuses stops the settings from loading with an error
that names the full dotted key, its file and line, and the command that removes it (#2201).

Before, the error was the validation error of pydantic. It named the section `ai` and the last part
of the key, but not the file, the line or a way to remove the key.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from devops_cli.config.round_trip import KeyPath
from devops_cli.config.settings import Settings, load_settings, reset_settings_cache
from devops_cli.config.unknown_keys import unknown_keys_error
from devops_cli.exceptions import ConfigurationError

_WITH_REMOVED_KEY = """\
# devops-cli settings of this workstation
telemetry:
  enabled: false

ai:
  # The model of every task that does not set its own.
  provider: ollama
  vllm_url: http://192.0.2.10:8000
  model: qwen3
"""


def _use(config_path: Path, text: str) -> None:
    """Make `text` the content of the active config file."""
    config_path.write_text(text, encoding="utf-8")
    reset_settings_cache()


def _load_error() -> ConfigurationError:
    """The configuration error that loading the settings raises."""
    with pytest.raises(ConfigurationError) as raised:
        load_settings()
    return raised.value


def _refusing_sections(model: type[BaseModel] = Settings, prefix: KeyPath = ()) -> list[KeyPath]:
    """The key path of each settings section that refuses a key it does not declare."""
    found: list[KeyPath] = []
    for name, field in model.model_fields.items():
        section = field.annotation
        if isinstance(section, type) and issubclass(section, BaseModel):
            path = (*prefix, name)
            if section.model_config.get("extra") == "forbid":
                found.append(path)
            found += _refusing_sections(section, path)
    return found


def _nested(path: KeyPath, leaf: str) -> str:
    """The YAML text that holds `leaf: 1` under the sections of `path`, after the telemetry lines."""
    lines = ["telemetry:", "  enabled: false"]
    lines += [f"{'  ' * depth}{part}:" for depth, part in enumerate(path)]
    lines.append(f"{'  ' * len(path)}{leaf}: 1")
    return "\n".join(lines) + "\n"


def test_a_key_that_a_release_removed_names_its_file_line_release_and_the_unset_command(
    isolate_devops_cli_config: Path,
) -> None:
    """`ai.vllm_url` is on line 8. Release 0.2.34 removed the setting, and the table of removed
    keys says so."""
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)

    error = _load_error()

    assert (error.message, error.exit_code, error.error_code) == (
        f"Unknown configuration key 'ai.vllm_url' at {isolate_devops_cli_config}:8. "
        "Release 0.2.34 removed it. Remove it with: devops config unset ai.vllm_url",
        1,
        "CONFIGURATION_ERROR",
    )


def test_the_sections_that_refuse_an_unknown_key_are_ai_its_tasks_and_each_task() -> None:
    """The next test writes an unknown key into each of these sections."""
    assert _refusing_sections() == [
        ("ai",),
        ("ai", "tasks"),
        ("ai", "tasks", "chat"),
        ("ai", "tasks", "metadata"),
        ("ai", "tasks", "analysis"),
        ("ai", "tasks", "verification"),
        ("ai", "tasks", "compose"),
        ("ai", "tasks", "embedding"),
    ]


@pytest.mark.parametrize("section", _refusing_sections(), ids=".".join)
def test_an_unknown_key_in_each_refusing_section_names_its_full_key_and_line(
    isolate_devops_cli_config: Path, section: KeyPath
) -> None:
    """The key line is the last line of the file: two telemetry lines, a line for each section
    on the path, then the key."""
    key = ".".join((*section, "no_such_key"))
    _use(isolate_devops_cli_config, _nested(section, "no_such_key"))

    error = _load_error()

    assert error.message == (
        f"Unknown configuration key '{key}' at {isolate_devops_cli_config}:{len(section) + 3}. "
        f"Remove it with: devops config unset {key}"
    )


def test_two_unknown_keys_each_get_a_line_of_the_error(isolate_devops_cli_config: Path) -> None:
    _use(
        isolate_devops_cli_config,
        "ai:\n  vllm_url: http://192.0.2.10:8000\n  tasks:\n    chat:\n      no_such_key: 1\n",
    )

    error = _load_error()

    assert error.message.splitlines() == [
        f"Unknown configuration key 'ai.vllm_url' at {isolate_devops_cli_config}:2. "
        "Release 0.2.34 removed it. Remove it with: devops config unset ai.vllm_url",
        f"Unknown configuration key 'ai.tasks.chat.no_such_key' at {isolate_devops_cli_config}:5. "
        "Remove it with: devops config unset ai.tasks.chat.no_such_key",
    ]


def test_a_key_in_the_file_that_is_not_active_names_that_file_in_the_unset_command(
    tmp_path: Path,
) -> None:
    """`devops config unset` edits the active file, so for a key in the other config file the
    command names that file through `DEVOPS_CLI_CONFIG`."""
    active = tmp_path / "project" / "config.yaml"
    other = tmp_path / "global" / "config.yaml"
    active.parent.mkdir()
    other.parent.mkdir()
    active.write_text("github:\n  default_org: example-org\n", encoding="utf-8")
    other.write_text("github:\n  default_org: example-org\nai:\n  vllm_url: x\n", encoding="utf-8")

    error = unknown_keys_error([("ai", "vllm_url")], (active, other), active=active)

    assert error.message == (
        f"Unknown configuration key 'ai.vllm_url' at {other}:4. Release 0.2.34 removed it. "
        f"Remove it with: DEVOPS_CLI_CONFIG={other} devops config unset ai.vllm_url"
    )
