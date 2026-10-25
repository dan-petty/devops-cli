"""A removal of a key from the config file deletes the lines of the key alone, keeps a copy of the
file and records the change, also when the settings do not load because of that key (#2201).

Before, `devops config` had no way to remove a key, so a person edited the file by hand to remove a
key that stopped every command from loading the settings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from devops_cli.config.settings import load_settings, remove_config_key, reset_settings_cache
from devops_cli.exceptions import ConfigurationError
from devops_cli.models.config import ConfigKeyRemoval
from tests.support.config_writes import written_keys
from tests.support.fakes.clock import ClockFake

_REMOVED_AT = datetime(2026, 10, 24, 23, 30, 5, tzinfo=UTC)
_STAMP = "20261024-233005"
_REMOVED_LINE = "  vllm_url: http://192.0.2.10:8000\n"
_WITH_REMOVED_KEY = f"""\
# devops-cli settings of this workstation
telemetry:
  enabled: false

ai:
  # The model of every task that does not set its own.
  provider: ollama
{_REMOVED_LINE}  model: qwen3   # the model of the chat task too
  tasks:
    chat:
      context_window: 16384

# The section of the GitHub owner.
github:
  default_org: example-org
"""


def _use(config_path: Path, text: str) -> None:
    """Make `text` the content of the active config file."""
    config_path.write_text(text, encoding="utf-8")
    reset_settings_cache()


def _diff(path: Path, hunk: str, removed: str) -> str:
    """The unified diff, with no context lines, of a removal of the `removed` lines."""
    lines = "".join(f"-{line}\n" for line in removed.splitlines())
    return f"--- {path}\n+++ {path}\n@@ {hunk} @@\n{lines}"


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


def test_a_removal_deletes_the_key_that_stops_the_load_and_keeps_every_other_line(
    isolate_devops_cli_config: Path, isolate_data_dir: Path, clock: ClockFake
) -> None:
    """The file before the removal is in the copy, the audit record names the removed key, and the
    settings load again."""
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)
    with pytest.raises(ConfigurationError):
        load_settings()
    clock.move_to(_REMOVED_AT)
    backup = isolate_devops_cli_config.with_name(f"config.yaml.bak-{_STAMP}")

    removal = remove_config_key("ai.vllm_url")

    assert removal == ConfigKeyRemoval(
        path=str(isolate_devops_cli_config),
        key="ai.vllm_url",
        line=8,
        diff=_diff(isolate_devops_cli_config, "-8 +7,0", _REMOVED_LINE),
        backup=str(backup),
    )
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_REMOVED_KEY.replace(
        _REMOVED_LINE, ""
    )
    assert backup.read_text(encoding="utf-8") == _WITH_REMOVED_KEY
    assert written_keys(isolate_data_dir) == [["ai.vllm_url"]]
    assert load_settings().ai.model == "qwen3"


def test_a_removal_of_a_section_deletes_each_line_of_it(isolate_devops_cli_config: Path) -> None:
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY.replace(_REMOVED_LINE, ""))

    removal = remove_config_key("ai.tasks")

    assert (removal.key, removal.line, isolate_devops_cli_config.read_text(encoding="utf-8")) == (
        "ai.tasks",
        9,
        _WITH_REMOVED_KEY.replace(_REMOVED_LINE, "").replace(
            "  tasks:\n    chat:\n      context_window: 16384\n", ""
        ),
    )


def test_a_removal_finds_a_key_whose_name_holds_a_dot(isolate_devops_cli_config: Path) -> None:
    """A model name such as `qwen3.8:27b` is one key of `ai.gateway_weights`."""
    _use(
        isolate_devops_cli_config,
        "ai:\n  gateway_weights:\n    qwen3.8:27b: 2\n    gemma4:26b: 1\n",
    )

    removal = remove_config_key("ai.gateway_weights.qwen3.8:27b")

    assert (removal.key, removal.line, isolate_devops_cli_config.read_text(encoding="utf-8")) == (
        "ai.gateway_weights.qwen3.8:27b",
        3,
        "ai:\n  gateway_weights:\n    gemma4:26b: 1\n",
    )


def test_a_dry_run_returns_the_removal_and_writes_nothing(
    isolate_devops_cli_config: Path, isolate_data_dir: Path
) -> None:
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)

    removal = remove_config_key("ai.vllm_url", dry_run=True)

    assert removal == ConfigKeyRemoval(
        path=str(isolate_devops_cli_config),
        key="ai.vllm_url",
        line=8,
        diff=_diff(isolate_devops_cli_config, "-8 +7,0", _REMOVED_LINE),
        backup=None,
    )
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_REMOVED_KEY
    assert _names(isolate_devops_cli_config.parent) == ["config.yaml"]
    assert written_keys(isolate_data_dir) == []


@pytest.mark.parametrize("key", ["ai.no_such_key", "ai.provider.model", "no_such_section"])
def test_a_removal_refuses_a_key_that_the_file_does_not_hold(
    isolate_devops_cli_config: Path, isolate_data_dir: Path, key: str
) -> None:
    """`ai.provider` holds a value and no keys, so the file holds no `ai.provider.model`."""
    _use(isolate_devops_cli_config, _WITH_REMOVED_KEY)

    with pytest.raises(ConfigurationError) as raised:
        remove_config_key(key)

    assert (raised.value.message, raised.value.exit_code, raised.value.error_code) == (
        f"The config file {isolate_devops_cli_config} does not hold the key '{key}'. "
        "Nothing changed.",
        1,
        "CONFIGURATION_ERROR",
    )
    assert isolate_devops_cli_config.read_text(encoding="utf-8") == _WITH_REMOVED_KEY
    assert _names(isolate_devops_cli_config.parent) == ["config.yaml"]
    assert written_keys(isolate_data_dir) == []


def test_a_removal_from_a_file_that_does_not_exist_refuses_the_key(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    missing = project / "config.yaml"

    with pytest.raises(ConfigurationError) as raised:
        remove_config_key("ai.vllm_url", missing)

    assert (raised.value.message, _names(project)) == (
        f"The config file {missing} does not hold the key 'ai.vllm_url'. Nothing changed.",
        [],
    )


def test_a_removal_from_a_file_that_is_not_yaml_names_the_file_and_quotes_no_line(
    isolate_devops_cli_config: Path,
) -> None:
    """The text can hold a credential, so the error quotes none of it."""
    _use(isolate_devops_cli_config, "ai:\n  api_key: FAKE-value: x\n")

    with pytest.raises(ConfigurationError) as raised:
        remove_config_key("ai.api_key")

    assert (raised.value.message, raised.value.exit_code) == (
        f"Cannot read {isolate_devops_cli_config}: it is not valid YAML (ScannerError).",
        1,
    )
